import requests
import pandas as pd
import time
import json
from datetime import datetime


class BigdatisImmeubleScraper:
    def __init__(self, test_mode=False, max_properties=20):
        self.search_url = "https://server.bigdatis.tn/api/properties/search"
        self.detail_url = "https://server.bigdatis.tn/api/properties/show"
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Origin': 'https://bigdatis.tn',
            'Referer': 'https://bigdatis.tn/'
        }

        self.all_data = []
        self.test_mode = test_mode
        self.max_properties = max_properties if test_mode else float('inf')

        # Tous les types d'immeubles
        if test_mode:
            # En mode test, seulement immeubles résidentiels pour aller plus vite
            self.property_types = {
                'residentialBuilding': 'Immeuble résidentiel',
            }
        else:
            # Mode complet: tous les types
            self.property_types = {
                'residentialBuilding': 'Immeuble résidentiel',
                'officeBuilding': 'Immeuble de bureaux'
            }

    def create_payload(self, property_type, page):
        return {
            "filter": {
                "agencies": [],
                "area": {"min": None, "max": None, "excludeMissing": False},
                "contactHasPhone": False,
                "excludedFlags": [],
                "includedFlags": [],
                "location": {"id": None, "additionalIds": []},
                "price": {"min": None, "max": None, "excludeMissing": False},
                "propertyFilters": [
                    {"property": "transactionType", "values": ["sale"]},
                    {"property": "propertyType", "values": [property_type]}
                ]
            },
            "orderBy": "date",
            "page": page,
            "limit": 100
        }

    def fetch_property_details(self, property_id):
        """Fetch detailed information for a single property"""
        try:
            url = f"{self.detail_url}/{property_id}"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f" [détail {property_id} error: {response.status_code}]", end="", flush=True)
                return None
                    
        except Exception as e:
            print(f" [détail {property_id} exception: {str(e)[:30]}]", end="", flush=True)
            return None

    def fetch_property_sources(self, property_id):
        """Fetch complete source information with URLs"""
        try:
            url = f"{self.detail_url}/{property_id}/sources"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                    
        except Exception as e:
            return None

    def scrape_property_type(self, property_type, type_name, fetch_details=True):
        mode_label = f"TEST - MAX {self.max_properties}" if self.test_mode else "COMPLET"
        print("\n" + "=" * 70)
        print(f"🏢 SCRAPING {mode_label}: {type_name.upper()}")
        if fetch_details:
            print("🔗 MODE: Fetching full details with sources and URLs")
        print("=" * 70)

        data = []
        page = 1
        seen_ids = set()
        max_retries = 3
        start_time = time.time()
        sources_count = 0
        sources_with_urls = 0

        while len(data) < self.max_properties:
            payload = self.create_payload(property_type, page)

            try:
                print(f"📡 Page {page}...", end=" ", flush=True)

                for attempt in range(max_retries):
                    try:
                        response = requests.post(
                            self.search_url,
                            headers=self.headers,
                            json=payload,
                            timeout=60
                        )
                        response.raise_for_status()
                        break
                    except requests.exceptions.Timeout:
                        time.sleep(2 ** attempt)
                else:
                    print("❌ API timeout")
                    break

                payload_json = response.json()

                if isinstance(payload_json, dict):
                    annonces = payload_json.get("results", [])
                elif isinstance(payload_json, list):
                    annonces = payload_json
                else:
                    annonces = []

                if not annonces:
                    print("❌ Vide – Fin")
                    break

                current_ids = {a.get("id") for a in annonces}
                new_ids = current_ids - seen_ids

                if page > 1 and not new_ids:
                    print("⚠️  Pages répétées – Fin")
                    break

                print(f"✅ {len(annonces)} annonces ({len(new_ids)} nouvelles)", end="")
                seen_ids.update(current_ids)

                for i, annonce in enumerate(annonces):
                    # Stop if we've reached the limit (only in test mode)
                    if len(data) >= self.max_properties:
                        print(f"\n   🎯 LIMITE ATTEINTE: {int(self.max_properties)} annonces")
                        break
                        
                    if annonce.get("id") in new_ids:
                        # Fetch full details if enabled
                        if fetch_details:
                            if self.test_mode:
                                # Verbose output in test mode
                                print(f"\n   └─ [{len(data)+1}/{int(self.max_properties)}] ID: {annonce.get('id')}", end="", flush=True)
                            
                            # Get property details
                            detailed_data = self.fetch_property_details(annonce.get("id"))
                            if detailed_data:
                                annonce = detailed_data
                                if self.test_mode:
                                    print(" ✓détail", end="", flush=True)
                            time.sleep(0.2)  # Small delay to avoid rate limiting
                            
                            # Get complete sources with URLs
                            sources_data = self.fetch_property_sources(annonce.get("id"))
                            if sources_data:
                                # Merge sources data (sources_data has URLs)
                                annonce["sources_with_urls"] = sources_data
                                sources_with_urls += len(sources_data)
                                if self.test_mode:
                                    print(f" ✓sources({len(sources_data)})", end="", flush=True)
                            time.sleep(0.2)
                            
                            if detailed_data and detailed_data.get("sources"):
                                sources_count += len(detailed_data.get("sources", []))
                            
                            # Show progress periodically in non-test mode
                            if not self.test_mode and (i + 1) % 10 == 0:
                                print(f"\n   └─ Progression: {len(data)+1} annonces traitées", end="", flush=True)
                        
                        row = self.process_annonce(annonce, page, type_name)
                        if row:
                            data.append(row)
                            if self.test_mode:
                                print(f" ✓saved", end="", flush=True)

                if self.test_mode:
                    print(f"\n   📊 Progression: {len(data)}/{int(self.max_properties)} | Sources: {sources_count} ({sources_with_urls} avec URLs)")
                else:
                    print(f" | Sources: {sources_count} ({sources_with_urls} avec URLs)")

                # Stop if we have enough data
                if len(data) >= self.max_properties:
                    break

                if len(annonces) < 100:
                    print("✅ Dernière page")
                    break

                page += 1
                time.sleep(1.5 if not self.test_mode else 1)  # Pause between pages

            except Exception as e:
                print(f"\n❌ Erreur: {e}")
                import traceback
                traceback.print_exc()
                break

        elapsed = time.time() - start_time
        print(f"\n✅ {type_name}: {len(data):,} annonces en {elapsed:.1f}s")
        return data

    def process_annonce(self, annonce, page, type_name):
        try:
            properties = annonce.get("properties", {})

            # Extract sources - prioritize sources_with_urls if available
            sources = []
            
            # First, try to use the detailed sources with URLs
            if "sources_with_urls" in annonce:
                raw_sources = annonce.get("sources_with_urls", [])
            else:
                raw_sources = annonce.get("sources", [])
            
            if isinstance(raw_sources, list) and len(raw_sources) > 0:
                for src in raw_sources:
                    source_entry = {
                        "sourceId": src.get("sourceId"),
                        "url": src.get("url"),  # This will be populated from /sources endpoint
                        "price": src.get("price"),
                        "sellerType": src.get("sellerType"),
                    }
                    
                    if src.get("lastModified"):
                        try:
                            source_entry["lastModified"] = datetime.fromtimestamp(
                                src.get("lastModified")
                            ).strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            source_entry["lastModified"] = src.get("lastModified")
                    else:
                        source_entry["lastModified"] = None
                    
                    sources.append(source_entry)

            # Extract images - prioritize imageUrls from detailed endpoint
            images = []
            if "imageUrls" in annonce and isinstance(annonce["imageUrls"], list):
                images = annonce["imageUrls"]
            elif "images" in annonce and isinstance(annonce["images"], list):
                for img in annonce["images"]:
                    if isinstance(img, dict) and img.get("url"):
                        images.append(img.get("url"))
                    elif isinstance(img, str):
                        images.append(img)

            # Extract detailed images with metadata if available
            images_detailed = []
            if "images" in annonce and isinstance(annonce["images"], list):
                for img in annonce["images"]:
                    if isinstance(img, dict):
                        images_detailed.append({
                            "url": img.get("url"),
                            "sourceId": img.get("sourceId"),
                            "adUrl": img.get("adUrl")
                        })

            # Extract contacts
            contacts = []
            if "contacts" in annonce and isinstance(annonce["contacts"], list):
                for contact in annonce["contacts"]:
                    contacts.append({
                        "sellerType": contact.get("sellerType"),
                        "contactName": contact.get("contactName"),
                        "active": contact.get("active")
                    })

            return {
                "id": annonce.get("id"),
                "titre": annonce.get("title", "").strip(),
                "description": annonce.get("description", "").strip(),
                "prix": annonce.get("price"),
                "surface": annonce.get("area"),
                "type_immeuble": type_name,
                "type_immeuble_code": properties.get("propertyType"),
                "type_transaction": properties.get("transactionType", "sale"),
                "type_vendeur": properties.get("sellerType"),
                "location_id": annonce.get("locationId"),
                "thumbnail_url": annonce.get("thumbnailUrl"),
                "image_urls": json.dumps(images, ensure_ascii=False),
                "images_detailed": json.dumps(images_detailed, ensure_ascii=False) if images_detailed else None,
                "sources": json.dumps(sources, ensure_ascii=False),
                "contacts": json.dumps(contacts, ensure_ascii=False),
                "nb_sources": len(sources),
                "nb_sources_with_urls": len([s for s in sources if s.get("url")]),
                "nb_contacts": len(contacts),
                "nb_contacts_actifs": annonce.get("activeContactsCount", 0),
                "nb_ads_total": annonce.get("adsCount", 0),
                "nb_ads_actifs": annonce.get("activeAdsCount", 0),
                "flags": json.dumps(annonce.get("flags", []), ensure_ascii=False),
                "first_seen_at": datetime.fromtimestamp(annonce.get("firstSeenAt")).strftime("%Y-%m-%d %H:%M:%S") if annonce.get("firstSeenAt") else None,
                "created_at": datetime.fromtimestamp(annonce.get("createdAt")).strftime("%Y-%m-%d %H:%M:%S") if annonce.get("createdAt") else None,
                "modified_at": datetime.fromtimestamp(annonce.get("modifiedAt")).strftime("%Y-%m-%d %H:%M:%S") if annonce.get("modifiedAt") else None,
                "price_dropped_at": datetime.fromtimestamp(annonce.get("priceDroppedAt")).strftime("%Y-%m-%d %H:%M:%S") if annonce.get("priceDroppedAt") else None,
                "page": page,
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            print(f"❌ Erreur annonce {annonce.get('id')}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def scrape_all_properties(self, fetch_details=True):
        for code, name in self.property_types.items():
            data = self.scrape_property_type(code, name, fetch_details)
            self.all_data.extend(data)
            print(f"📊 Total cumulé : {len(self.all_data):,} annonces")
            
            # Stop if we've reached the limit (only in test mode)
            if self.test_mode and len(self.all_data) >= self.max_properties:
                break
            
            time.sleep(2)

        self.save_data()

    def save_data(self):
        if not self.all_data:
            print("⚠️  Aucune donnée")
            return

        df = pd.DataFrame(self.all_data)
        df.drop_duplicates(subset=["id"], inplace=True)

        df["prix"] = pd.to_numeric(df["prix"], errors="coerce")
        df["surface"] = pd.to_numeric(df["surface"], errors="coerce")

        mode_suffix = "TEST" if self.test_mode else "FULL"
        filename = f"bigdatis_immeubles_{mode_suffix}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        df.to_csv(filename, index=False, encoding="utf-8-sig")

        print("\n" + "=" * 70)
        print(f"💾 FICHIER {'TEST ' if self.test_mode else ''}SAUVEGARDÉ")
        print("=" * 70)
        print(f"📁 {filename}")
        print(f"📊 Total annonces : {len(df):,}")
        
        # Show sample data in test mode
        if self.test_mode:
            print("\n📋 APERÇU DES DONNÉES (5 premières annonces):")
            print("-" * 70)
            for idx, row in df.head(5).iterrows():
                print(f"\n{idx+1}. ID: {row['id']} | {row['titre'][:60]}...")
                if pd.notna(row['prix']) and pd.notna(row['surface']):
                    print(f"   Prix: {row['prix']:,.0f} DT | Surface: {row['surface']:,.0f} m²")
                    if row['surface'] > 0:
                        print(f"   Prix/m²: {row['prix']/row['surface']:,.0f} DT/m²")
                else:
                    print(f"   Prix/Surface: N/A")
                print(f"   Sources: {row['nb_sources']} ({row['nb_sources_with_urls']} avec URLs)")
                print(f"   Images: {len(json.loads(row['image_urls']))} | Contacts: {row['nb_contacts']}")
            print("-" * 70)
        
        # Statistics by property type
        print("\n📊 Répartition par type d'immeuble:")
        for immeuble_type in df["type_immeuble"].unique():
            count = len(df[df["type_immeuble"] == immeuble_type])
            avg_surface = df[df["type_immeuble"] == immeuble_type]["surface"].mean()
            avg_price = df[df["type_immeuble"] == immeuble_type]["prix"].mean()
            print(f"   • {immeuble_type}: {count:,} annonces")
            if not pd.isna(avg_surface):
                print(f"     └─ Surface moyenne: {avg_surface:.0f} m²")
            if not pd.isna(avg_price):
                print(f"     └─ Prix moyen: {avg_price:,.0f} DT")
        
        # Statistics about sources
        with_sources = df[df["nb_sources"] > 0].shape[0]
        total_sources = df["nb_sources"].sum()
        avg_sources = df["nb_sources"].mean() if len(df) > 0 else 0
        
        # Sources with URLs
        with_urls = df[df["nb_sources_with_urls"] > 0].shape[0]
        total_urls = df["nb_sources_with_urls"].sum()
        
        print(f"\n🔗 Statistiques des sources:")
        print(f"   • Annonces avec sources : {with_sources:,} / {len(df):,} ({with_sources/len(df)*100:.1f}%)")
        print(f"   • Total sources : {int(total_sources):,}")
        print(f"   • Moyenne sources/annonce : {avg_sources:.2f}")
        if total_sources > 0:
            print(f"   • Sources avec URLs : {int(total_urls):,} ({total_urls/total_sources*100:.1f}% des sources)")
            print(f"   • Annonces avec URLs : {with_urls:,} / {len(df):,} ({with_urls/len(df)*100:.1f}%)")
        
        # Price statistics
        print(f"\n💰 Statistiques prix:")
        with_price = df[df["prix"].notna()]
        if len(with_price) > 0:
            print(f"   • Annonces avec prix : {len(with_price):,} / {len(df):,} ({len(with_price)/len(df)*100:.1f}%)")
            print(f"   • Prix moyen : {with_price['prix'].mean():,.0f} DT")
            print(f"   • Prix médian : {with_price['prix'].median():,.0f} DT")
            print(f"   • Prix min : {with_price['prix'].min():,.0f} DT")
            print(f"   • Prix max : {with_price['prix'].max():,.0f} DT")
        
        # Surface statistics
        print(f"\n📐 Statistiques surface:")
        with_surface = df[df["surface"].notna()]
        if len(with_surface) > 0:
            print(f"   • Annonces avec surface : {len(with_surface):,} / {len(df):,} ({len(with_surface)/len(df)*100:.1f}%)")
            print(f"   • Surface moyenne : {with_surface['surface'].mean():,.1f} m²")
            print(f"   • Surface médiane : {with_surface['surface'].median():,.1f} m²")
            print(f"   • Surface min : {with_surface['surface'].min():,.0f} m²")
            print(f"   • Surface max : {with_surface['surface'].max():,.0f} m²")
        
        # Price per m² statistics
        df_prix_m2 = df[(df["prix"].notna()) & (df["surface"].notna()) & (df["surface"] > 0)]
        if len(df_prix_m2) > 0:
            df_prix_m2.loc[:, "prix_m2"] = df_prix_m2["prix"] / df_prix_m2["surface"]
            print(f"\n💵 Prix au m²:")
            print(f"   • Prix/m² moyen : {df_prix_m2['prix_m2'].mean():,.0f} DT/m²")
            print(f"   • Prix/m² médian : {df_prix_m2['prix_m2'].median():,.0f} DT/m²")
            print(f"   • Prix/m² min : {df_prix_m2['prix_m2'].min():,.0f} DT/m²")
            print(f"   • Prix/m² max : {df_prix_m2['prix_m2'].max():,.0f} DT/m²")
        
        # Contact statistics
        print(f"\n📞 Statistiques contacts:")
        with_contacts = df[df["nb_contacts"] > 0].shape[0]
        total_contacts = df["nb_contacts"].sum()
        active_contacts = df["nb_contacts_actifs"].sum()
        if with_contacts > 0:
            print(f"   • Annonces avec contacts : {with_contacts:,} / {len(df):,} ({with_contacts/len(df)*100:.1f}%)")
            print(f"   • Total contacts : {int(total_contacts):,}")
            print(f"   • Contacts actifs : {int(active_contacts):,}")
        
        # Seller type statistics
        print(f"\n👤 Type de vendeur:")
        vendeur_stats = df["type_vendeur"].value_counts()
        for vendeur, count in vendeur_stats.items():
            pct = (count/len(df))*100
            nom = 'Particulier' if vendeur == 'private' else 'Agence' if vendeur == 'agency' else vendeur
            print(f"   • {nom:<15} : {count:>6,} ({pct:>5.1f}%)")
        
        # Show sample of sources in test mode
        if self.test_mode and with_sources > 0:
            print("\n📋 Exemple de sources (3 premières annonces):")
            sample = df[df["nb_sources"] > 0].head(3)
            for idx, row in sample.iterrows():
                sources = json.loads(row["sources"])
                print(f"\n  ID {row['id']}: {row['titre'][:50]}...")
                for src in sources[:2]:  # Show first 2 sources
                    print(f"    • {src.get('url', 'N/A')[:70]}...")
        
        print("=" * 70)


if __name__ == "__main__":
    print("=" * 70)
    print("🏢 BIGDATIS SCRAPER - IMMEUBLES")
    print("=" * 70)
    print("\nTypes d'immeubles disponibles:")
    print("  • Immeuble résidentiel (residentialBuilding)")
    print("  • Immeuble de bureaux (officeBuilding)")
    print("\nDonnées récupérées:")
    print("  ✓ Informations de base (titre, prix, surface)")
    print("  ✓ Descriptions complètes")
    print("  ✓ Toutes les images avec métadonnées")
    print("  ✓ Sources complètes avec URLs")
    print("  ✓ Contacts avec statut")
    print("  ✓ Dates et historique")
    
    print("\n" + "=" * 70)
    print("MODE DE SCRAPING:")
    print("=" * 70)
    print("1. Mode TEST - 20 annonces (rapide, pour tester)")
    print("2. Mode COMPLET - Toutes les annonces (peut prendre du temps)")
    print()
    
    mode_choice = input("Votre choix [1]: ").strip()
    
    if mode_choice == "2":
        # Mode complet
        scraper = BigdatisImmeubleScraper(test_mode=False)
        print("\n✅ MODE COMPLET sélectionné")
        print("⚠️  ATTENTION: Le scraping complet peut prendre du temps")
        print("   et va récupérer toutes les annonces d'immeubles disponibles.")
        
        confirm = input("\n➡️ Confirmer le scraping complet ? (oui/non) [non]: ").strip().lower()
        if confirm not in ["oui", "o", "y", "yes"]:
            print("❌ Scraping annulé")
            exit()
    else:
        # Mode test (par défaut)
        scraper = BigdatisImmeubleScraper(test_mode=True, max_properties=20)
        print("\n✅ MODE TEST sélectionné (20 annonces)")
    
    response = input("\n➡️ Lancer le scraping ? (oui/non) [oui]: ").strip().lower()

    if response in ["", "oui", "o", "y", "yes"]:
        mode_label = "TEST" if scraper.test_mode else "COMPLET"
        print(f"\n🚀 Démarrage du scraping en mode {mode_label}...")
        scraper.scrape_all_properties(fetch_details=True)
        print(f"\n✅ Scraping {mode_label} terminé avec succès!")
        
        if scraper.test_mode:
            print("\n💡 Le test est réussi ! Pour scraper toutes les annonces,")
            print("   relancez le script et choisissez l'option 2 (Mode COMPLET).")
    else:
        print("❌ Scraping annulé")