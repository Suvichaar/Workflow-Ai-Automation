# ================== 📦 Install First ==================
# pip install streamlit simple_image_download requests beautifulsoup4 pandas

# ================== 📋 Import ==================
import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import csv
import time
import pandas as pd
from urllib.parse import urlparse
import io
from simple_image_download import simple_image_download as simp
import zipfile
import os
import shutil

# ================== 📘 Tab Setup ==================
tab1, tab2 = st.tabs(["📄 Quote Scraper", "🖼️ Bulk Image Downloader"])

# ================== 📄 QuoteFancy Scraper in tab1 ==================
with tab1:
    st.title("📝 QuoteFancy Scraper")

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.93 Safari/537.36"
    )
    REQUEST_TIMEOUT = 10
    DELAY_BETWEEN_PAGES = 1
    MAX_PAGES = 10

    def create_session_with_retries():
        session = requests.Session()
        session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept-Language': 'en-US,en;q=0.9'
        })
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def extract_slug_from_url(url):
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        return path.split("/")[0] if path else ""

    def scrape_quotes_for_slug(slug, max_pages=MAX_PAGES):
        session = create_session_with_retries()
        rows, serial_number = [], 1

        for page_number in range(1, max_pages + 1):
            page_url = f"https://quotefancy.com/{slug}/page/{page_number}"
            try:
                response = session.get(page_url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
            except requests.RequestException:
                break

            soup = BeautifulSoup(response.content, "html.parser")
            containers = soup.find_all("div", class_="q-wrapper")
            if not containers:
                break

            for container in containers:
                quote_div = container.find("div", class_="quote-a")
                quote_text = quote_div.get_text(strip=True) if quote_div else container.find("a", class_="quote-a").get_text(strip=True)

                quote_link = ""
                if quote_div and quote_div.find("a"):
                    quote_link = quote_div.find("a").get("href", "")
                elif container.find("a", class_="quote-a"):
                    quote_link = container.find("a", class_="quote-a").get("href", "")

                author_div = container.find("div", class_="author-p bylines")
                if author_div:
                    author_text = author_div.get_text(strip=True).replace("by ", "").strip()
                else:
                    author_p = container.find("p", class_="author-p")
                    author_text = author_p.find("a").get_text(strip=True) if author_p and author_p.find("a") else "Anonymous"

                rows.append([serial_number, quote_text, quote_link, author_text])
                serial_number += 1

            time.sleep(DELAY_BETWEEN_PAGES)

        return rows

    def convert_to_csv_buffer(rows):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Serial No", "Quote", "Link", "Author"])
        writer.writerows(rows)
        return output.getvalue()

    input_urls = st.text_area("Enter QuoteFancy URLs (comma separated):")
    filename = st.text_input("Filename to save as (.csv)", "quotes.csv")

    if st.button("Start Scraping", key="scrape_button"):
        if not input_urls or not filename:
            st.error("Please provide both URLs and filename.")
        else:
            url_list = [url.strip() for url in input_urls.split(",") if url.strip()]
            all_quotes = []
            for url in url_list:
                slug = extract_slug_from_url(url)
                st.write(f"🔍 Scraping: `{slug}`")
                all_quotes.extend(scrape_quotes_for_slug(slug))

            if all_quotes:
                csv_data = convert_to_csv_buffer(all_quotes)
                st.success(f"✅ Scraped {len(all_quotes)} quotes.")
                st.download_button("📥 Download CSV", data=csv_data, file_name=filename, mime='text/csv')

                df = pd.DataFrame(all_quotes, columns=["Serial No", "Quote", "Link", "Author"])
                distinct_authors = df["Author"].drop_duplicates().sort_values().tolist()
                authors_comma_str = ", ".join(distinct_authors)

                st.markdown("### 👤 Distinct Authors Found")
                st.text(authors_comma_str)
            else:
                st.warning("⚠️ No quotes scraped.")

# ================== 🖼️ Bulk Image Downloader in tab2 ==================
with tab2:
    
    st.title("🖼️ Bulk Image Downloader + S3 CDN Uploader")

    import boto3
    import io
    import zipfile
    import os
    import shutil
    import csv
    from simple_image_download import simple_image_download as simp

    # AWS Config
    aws_access_key = st.secrets["aws_access_key"]
    aws_secret_key = st.secrets["aws_secret_key"]
    region_name = "ap-south-1"
    bucket_name = "suvichaarapp"
    s3_prefix = "media/"
    cdn_base_url = "https://media.suvichaar.org/"

    # Boto3 client setup
    s3 = boto3.client("s3",
                      aws_access_key_id=aws_access_key,
                      aws_secret_access_key=aws_secret_key,
                      region_name=region_name)

    keywords_input = st.text_input("Enter comma-separated keywords", "cat,dog,car")
    count = st.number_input("Number of images per keyword", min_value=1, value=5)

    if st.button("Download & Upload Images", key="img_button"):
        keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
        response = simp.simple_image_download

        # Clean previous folder
        if os.path.exists("simple_images"):
            shutil.rmtree("simple_images")

        # Download Images
        for keyword in keywords:
            st.write(f"🔍 Downloading `{count}` images for: **{keyword}**")
            response().download(keyword, count)

        # Upload to S3 + collect info
        upload_info = []
        for foldername, _, filenames in os.walk("simple_images"):
            for filename in filenames:
                filepath = os.path.join(foldername, filename)
                keyword_folder = os.path.basename(foldername)
                s3_key = f"{s3_prefix}{keyword_folder}/{filename}"
                try:
                    s3.upload_file(filepath, bucket_name, s3_key, ExtraArgs={"ACL": "public-read"})
                    cdn_url = f"{cdn_base_url}{s3_key}"
                    upload_info.append([keyword_folder, filename, cdn_url])
                except Exception as e:
                    st.error(f"❌ Upload failed for {filename}: {str(e)}")

        # Generate CSV in memory
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["Keyword", "Filename", "CDN_URL"])
        writer.writerows(upload_info)

        st.download_button(
            "📥 Download Image CDN CSV",
            data=csv_buffer.getvalue(),
            file_name="cdn_image_links.csv",
            mime="text/csv"
        )

        st.success("✅ All images uploaded and links generated!")
