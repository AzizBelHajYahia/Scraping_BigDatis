#!/usr/bin/env python3
"""
Bigdatis Scraper Orchestrator
Automate all scraping tasks with configurable options
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

# Import all scrapers
from bigdatis_residential_scraper import BigdatisLoopScraper
from bigdatis_bureaux_scraper import BigdatisBureauxScraper
from bigdatis_commercial_scraper import BigdatisCommercialScraper
from bigdatis_immeubles_scraper import BigdatisImmeublescraper
from bigdatis_terrin_scraper import BigdatisTerrainscraper


class ScraperOrchestrator:
    """Main orchestrator for all Bigdatis scrapers"""
    
    def __init__(self):
        self.scrapers = {
            'residential': {
                'class': BigdatisLoopScraper,
                'name': 'Résidentiel (Apparts, Maisons, Villas, Duplex)',
                'emoji': '🏘️'
            },
            'bureaux': {
                'class': BigdatisBureauxScraper,
                'name': 'Bureaux',
                'emoji': '🏢'
            },
            'commercial': {
                'class': BigdatisCommercialScraper,
                'name': 'Commercial & Industriel',
                'emoji': '🏭'
            },
            'immeubles': {
                'class': BigdatisImmeublescraper,
                'name': 'Immeubles',
                'emoji': '🏢'
            },
            'terrains': {
                'class': BigdatisTerrainscraper,
                'name': 'Terrains',
                'emoji': '🌾'
            }
        }
        self.results = {}
    
    def print_header(self):
        """Print main header"""
        print("\n" + "="*80)
        print("🚀 BIGDATIS SCRAPER ORCHESTRATOR".center(80))
        print("="*80)
        print(f"⏰ Démarrage : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
    
    def print_menu(self):
        """Print scraper selection menu"""
        print("\n📋 SCRAPERS DISPONIBLES :")
        print("-" * 80)
        for idx, (key, info) in enumerate(self.scrapers.items(), 1):
            print(f"  {idx}. {info['emoji']} {info['name']:<50} [{key}]")
        print(f"  {len(self.scrapers) + 1}. ⚡ TOUT scraper (mode automatique)")
        print("-" * 80)
    
    def run_scraper(self, scraper_key):
        """Run a single scraper"""
        if scraper_key not in self.scrapers:
            print(f"❌ Scraper inconnu: {scraper_key}")
            return False
        
        info = self.scrapers[scraper_key]
        print(f"\n{info['emoji']} Lancement : {info['name']}")
        print("-" * 80)
        
        start_time = time.time()
        
        try:
            scraper = info['class']()
            
            # Run the appropriate scraping method
            if scraper_key == 'residential':
                scraper.scrape_all_types()
            elif scraper_key == 'bureaux':
                scraper.scrape_bureaux()
            elif scraper_key == 'commercial':
                scraper.scrape_all_commercial()
            elif scraper_key == 'immeubles':
                scraper.scrape_all_buildings()
            elif scraper_key == 'terrains':
                scraper.scrape_all_terrains()
            
            elapsed = time.time() - start_time
            self.results[scraper_key] = {
                'status': 'success',
                'time': elapsed,
                'data_count': len(scraper.all_data) if hasattr(scraper, 'all_data') else len(scraper.data)
            }
            
            print(f"✅ {info['name']} terminé en {elapsed:.1f}s")
            return True
            
        except Exception as e:
            elapsed = time.time() - start_time
            self.results[scraper_key] = {
                'status': 'error',
                'time': elapsed,
                'error': str(e)
            }
            print(f"❌ Erreur lors du scraping {info['name']}: {e}")
            return False
    
    def run_all(self):
        """Run all scrapers sequentially"""
        print("\n⚡ MODE AUTOMATIQUE - TOUS LES SCRAPERS")
        print("="*80)
        
        total_start = time.time()
        
        for idx, scraper_key in enumerate(self.scrapers.keys(), 1):
            print(f"\n[{idx}/{len(self.scrapers)}] ", end="")
            self.run_scraper(scraper_key)
            
            # Pause between scrapers
            if idx < len(self.scrapers):
                print("\n⏸️  Pause 5s avant le prochain scraper...")
                time.sleep(5)
        
        total_time = time.time() - total_start
        
        # Print summary
        self.print_summary(total_time)
    
    def print_summary(self, total_time):
        """Print final summary"""
        print("\n" + "="*80)
        print("📊 RÉSUMÉ FINAL".center(80))
        print("="*80)
        
        success_count = sum(1 for r in self.results.values() if r['status'] == 'success')
        error_count = sum(1 for r in self.results.values() if r['status'] == 'error')
        total_data = sum(r.get('data_count', 0) for r in self.results.values() if r['status'] == 'success')
        
        print(f"\n✅ Réussis : {success_count}/{len(self.results)}")
        print(f"❌ Erreurs : {error_count}/{len(self.results)}")
        print(f"📈 Total annonces collectées : {total_data:,}")
        print(f"⏱️  Temps total : {total_time:.1f}s ({total_time/60:.1f} min)")
        
        print("\n📋 DÉTAILS PAR SCRAPER :")
        print("-" * 80)
        for key, result in self.results.items():
            info = self.scrapers[key]
            status_emoji = "✅" if result['status'] == 'success' else "❌"
            
            if result['status'] == 'success':
                print(f"  {status_emoji} {info['emoji']} {info['name']:<45} | "
                      f"{result['data_count']:>6,} annonces | {result['time']:>6.1f}s")
            else:
                print(f"  {status_emoji} {info['emoji']} {info['name']:<45} | "
                      f"ERREUR: {result.get('error', 'Unknown')[:30]}")
        
        print("="*80)
        print(f"🏁 Terminé : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")
    
    def interactive_mode(self):
        """Interactive mode with menu"""
        self.print_header()
        self.print_menu()
        
        try:
            choice = input("\n➡️  Votre choix (1-6) [6] : ").strip()
            
            if not choice or choice == str(len(self.scrapers) + 1):
                # Run all
                self.run_all()
            else:
                # Run specific scraper
                choice_idx = int(choice) - 1
                scraper_keys = list(self.scrapers.keys())
                
                if 0 <= choice_idx < len(scraper_keys):
                    scraper_key = scraper_keys[choice_idx]
                    start_time = time.time()
                    self.run_scraper(scraper_key)
                    self.print_summary(time.time() - start_time)
                else:
                    print("❌ Choix invalide")
                    sys.exit(1)
                    
        except KeyboardInterrupt:
            print("\n\n⚠️  Interruption utilisateur - Arrêt du scraping")
            sys.exit(0)
        except ValueError:
            print("❌ Entrée invalide")
            sys.exit(1)


def main():
    """Main entry point with CLI arguments"""
    parser = argparse.ArgumentParser(
        description='Bigdatis Scraper Orchestrator - Automatise tous les scrapers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python main.py                          # Mode interactif
  python main.py --all                    # Scraper tout automatiquement
  python main.py --scrapers residential   # Scraper uniquement le résidentiel
  python main.py --scrapers residential bureaux terrains  # Scrapers multiples
        """
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Lancer tous les scrapers automatiquement'
    )
    
    parser.add_argument(
        '--scrapers',
        nargs='+',
        choices=['residential', 'bureaux', 'commercial', 'immeubles', 'terrains'],
        help='Spécifier un ou plusieurs scrapers à lancer'
    )
    
    parser.add_argument(
        '--silent',
        action='store_true',
        help='Mode silencieux (moins de messages)'
    )
    
    args = parser.parse_args()
    
    orchestrator = ScraperOrchestrator()
    
    # CLI mode
    if args.all:
        orchestrator.print_header()
        orchestrator.run_all()
        
    elif args.scrapers:
        orchestrator.print_header()
        total_start = time.time()
        
        for scraper_key in args.scrapers:
            orchestrator.run_scraper(scraper_key)
            time.sleep(2)  # Pause between scrapers
        
        orchestrator.print_summary(time.time() - total_start)
        
    else:
        # Interactive mode
        orchestrator.interactive_mode()


if __name__ == "__main__":
    main()