import pandas as pd
import json
import requests
import os
from pathlib import Path
from urllib.parse import urlparse
import time
from datetime import datetime
import glob


class ImageDownloader:
    def __init__(self, output_dir="downloaded_images"):
        """Initialize the image downloader"""
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.downloaded = 0
        self.failed = 0
        self.skipped = 0
        
    def download_image(self, url, filepath):
        """Download a single image"""
        try:
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Create directory if needed
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save image
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
            
        except Exception as e:
            print(f"      ❌ Failed: {str(e)[:50]}")
            return False
    
    def get_file_extension(self, url):
        """Get file extension from URL"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Check for common image extensions
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif']:
            if ext in path:
                return ext
        
        # Default to .jpg
        return '.jpg'
    
    def process_csv(self, csv_file, max_images_per_property=None):
        """Process a CSV file and download all images"""
        
        print("\n" + "=" * 70)
        print(f"📂 Processing: {os.path.basename(csv_file)}")
        print("=" * 70)
        
        # Read CSV
        try:
            df = pd.read_csv(csv_file)
            print(f"✓ Loaded {len(df)} properties")
        except Exception as e:
            print(f"❌ Error reading CSV: {e}")
            return
        
        # Check for required columns
        if 'image_urls' not in df.columns:
            print("❌ No 'image_urls' column found")
            return
        
        # Count how many have images
        has_images = df['image_urls'].notna().sum()
        print(f"✓ {has_images} properties have images")
        
        # Process each property
        for idx, row in df.iterrows():
            property_id = row.get('id', idx)
            image_urls = row.get('image_urls')
            titre = row.get('titre', 'Unknown')
            
            # Show progress every 10 properties
            if (idx + 1) % 10 == 0:
                print(f"\n⏳ Progress: {idx + 1}/{len(df)} properties processed...")
            
            if pd.isna(image_urls):
                self.skipped += 1
                continue
            
            # Parse JSON array
            try:
                urls = json.loads(image_urls)
                if not isinstance(urls, list):
                    urls = [urls]
            except:
                print(f"\n⚠️  [{property_id}] Invalid image_urls format")
                self.skipped += 1
                continue
            
            # Skip if no URLs
            if not urls or len(urls) == 0:
                self.skipped += 1
                continue
            
            # Limit images if requested
            if max_images_per_property:
                urls = urls[:max_images_per_property]
            
            print(f"\n📸 [{idx + 1}/{len(df)}] Property {property_id}: {len(urls)} image(s)")
            print(f"   Title: {titre[:60]}...")
            
            # Create property directory
            property_dir = os.path.join(self.output_dir, str(property_id))
            
            # Download each image
            for img_idx, url in enumerate(urls, 1):
                ext = self.get_file_extension(url)
                filename = f"image_{img_idx:03d}{ext}"
                filepath = os.path.join(property_dir, filename)
                
                # Skip if already exists
                if os.path.exists(filepath):
                    self.skipped += 1
                    continue
                
                print(f"   ⬇️  [{img_idx}/{len(urls)}] {filename}: {url[:60]}...")
                
                if self.download_image(url, filepath):
                    self.downloaded += 1
                else:
                    self.failed += 1
                
                # Small delay to be polite
                time.sleep(0.3)
        
        print("\n" + "=" * 70)
        print(f"✅ Finished: {os.path.basename(csv_file)}")
        print("=" * 70)
    
    def process_multiple_csvs(self, csv_files, max_images_per_property=None):
        """Process multiple CSV files"""
        
        print("=" * 70)
        print("📥 BULK IMAGE DOWNLOADER")
        print("=" * 70)
        print(f"\nFiles to process: {len(csv_files)}")
        print(f"Output directory: {self.output_dir}")
        if max_images_per_property:
            print(f"Max images per property: {max_images_per_property}")
        print("=" * 70)
        
        start_time = time.time()
        
        for i, csv_file in enumerate(csv_files, 1):
            print(f"\n\n{'=' * 70}")
            print(f"FILE {i}/{len(csv_files)}")
            print('=' * 70)
            self.process_csv(csv_file, max_images_per_property)
        
        elapsed = time.time() - start_time
        
        print("\n\n" + "=" * 70)
        print("🎉 ALL DONE!")
        print("=" * 70)
        print(f"📊 Total downloaded: {self.downloaded}")
        print(f"❌ Total failed: {self.failed}")
        print(f"⏭️  Total skipped: {self.skipped}")
        print(f"⏱️  Time elapsed: {elapsed:.1f} seconds")
        print(f"📁 Images saved to: {os.path.abspath(self.output_dir)}")
        print("=" * 70)


def find_csv_files():
    """Find CSV files in data directory and subdirectories"""
    
    csv_files = []
    
    # Check data directory
    data_dir = "data"
    
    if os.path.exists(data_dir):
        # Find all CSV files in data directory
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if file.endswith('.csv'):
                    csv_files.append(os.path.join(root, file))
    
    # Also check current directory
    current_csvs = glob.glob("*.csv")
    csv_files.extend(current_csvs)
    
    return sorted(csv_files)


def main():
    print("=" * 70)
    print("📥 IMAGE DOWNLOADER FOR CSV FILES")
    print("=" * 70)
    print("\nThis script downloads images from the 'image_urls' column")
    print("Images are organized by property ID")
    print("=" * 70)
    
    # Find CSV files
    csv_files = find_csv_files()
    
    if not csv_files:
        print("\n❌ No CSV files found in current directory or data/")
        return
    
    print(f"\n📋 Found {len(csv_files)} CSV file(s):")
    for i, f in enumerate(csv_files, 1):
        file_size = os.path.getsize(f) / (1024 * 1024)  # MB
        print(f"   {i}. {f} ({file_size:.1f} MB)")
    
    # Ask user which files to process
    print("\n" + "=" * 70)
    print("Select files to process:")
    print("  - Press Enter to process ALL files")
    print("  - Enter numbers (comma-separated): 1,3,5")
    print("  - Enter range: 1-3")
    
    selection = input("\n➡️  Your choice: ").strip()
    
    if not selection:
        files_to_process = csv_files
        print(f"✅ Processing all {len(csv_files)} files")
    else:
        try:
            # Parse selection
            indices = []
            
            # Handle ranges (e.g., "1-3")
            if '-' in selection:
                start, end = selection.split('-')
                indices = list(range(int(start.strip()) - 1, int(end.strip())))
            else:
                # Handle comma-separated (e.g., "1,3,5")
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
            
            files_to_process = [csv_files[i] for i in indices]
            print(f"✅ Processing {len(files_to_process)} selected file(s)")
            
        except Exception as e:
            print(f"❌ Invalid selection: {e}")
            return
    
    # Ask for max images per property
    print("\n" + "=" * 70)
    print("Limit images per property?")
    max_imgs = input("Max images (leave empty for all): ").strip()
    max_images = int(max_imgs) if max_imgs else None
    
    # Ask for output directory
    print("\n" + "=" * 70)
    output_dir = input("Output directory [data/images]: ").strip()
    if not output_dir:
        output_dir = "data/images"
    
    # Confirm
    print("\n" + "=" * 70)
    print("📋 SUMMARY:")
    print(f"  📂 Files: {len(files_to_process)}")
    print(f"  📁 Output: {output_dir}")
    print(f"  📸 Max images: {max_images or 'All'}")
    print("\nFiles to process:")
    for f in files_to_process:
        print(f"  • {f}")
    print("=" * 70)
    
    confirm = input("\n▶️  Start download? (yes/no) [yes]: ").strip().lower()
    
    if confirm not in ["", "yes", "y", "oui", "o"]:
        print("❌ Cancelled")
        return
    
    # Start downloading
    print("\n🚀 Starting download...\n")
    downloader = ImageDownloader(output_dir)
    downloader.process_multiple_csvs(files_to_process, max_images)


if __name__ == "__main__":
    main()