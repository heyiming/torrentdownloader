#!/usr/bin/env python

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import urllib.request, urllib.error
import transmission_rpc
from pymongo import ASCENDING, MongoClient
import argparse

LABEL = "TORRENTDOWNLOADER"

def askURL(url):
    head = { 
        "User-Agent": "Mozilla / 5.0(Windows NT 10.0; Win64; x64) AppleWebKit / 537.36(KHTML, like Gecko) Chrome / 80.0.3987.122  Safari / 537.36"
    }
    
    request = urllib.request.Request(url, headers=head)
    html = ""
    try:
        response = urllib.request.urlopen(request)
        html = response.read().decode("utf-8")
    except urllib.error.URLError as e:
        if hasattr(e, "code"):
            print(e.code)
        if hasattr(e, "reason"):
            print(e.reason)
    return html

def fetch_download_links(url):
    html = askURL(url)
    
    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    # Find all <a> tags with an href attribute
    links = soup.find_all('a', href=True)

    # Extract download links (assuming they contain 'download' in the href)
    download_links = []
    for link in links:
        href = link['href']
        if href.endswith('.torrent'):
            # Convert relative URLs to absolute URLs
            full_url = urljoin(url, href)
            download_links.append(full_url)

    return download_links

def clean_up_download(client): 
    torrents = client.get_torrents()
    
    done_torrents = []
    for torrent in torrents:
        if torrent.status.stopped and LABEL in torrent.labels:
            print(f"Torrent id:{torrent.id} name:{torrent.name} is done. To remove.")
            done_torrents.append(torrent.id)
    
    if done_torrents:
        client.remove_torrent(ids = done_torrents)
    

def send_link_to_transmission(client, download_link):
    # Add the torrent or magnet link
    try:
        torrent = client.add_torrent(download_link, download_dir="/private", labels=[LABEL])
        print(f"Successfully added torrent: {torrent.name}")
    except transmission_rpc.error.TransmissionError as e:
        print(f"Failed to add torrent: {e}")

def save_to_mongodb(mongo_client, link):
    # Select the database
    db = mongo_client['torrentdownloader']

    # Select the collection
    collection = db['torrentdownloader']
    
    # Create a TTL index on the createdAt field with a 30-day expiration
    collection.create_index([("createdAt", ASCENDING)], expireAfterSeconds=2592000)

    if collection.find_one({"download_link": link}) is None:
        # Insert the download link into the collection
        collection.insert_one({"download_link": link})
        return True
    else:
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Torrent Downloader')
    parser.add_argument('-url', type=str, help='The base URL to fetch torrent links from')
    args = parser.parse_args()

    # Connect to the Transmission server
    tranmission_client = transmission_rpc.Client(
        host = "192.168.1.50"
    )
    mongo_client = MongoClient('mongodb://192.168.1.50:27017/')

    clean_up_download(tranmission_client)
    
    url = args.url
    for i in range(1, 5):
        download_links = fetch_download_links(url + str(i))
        for link in download_links:
            if (save_to_mongodb(mongo_client, link)):
                send_link_to_transmission(tranmission_client, link)
                print(f"Link sent to transmission: {link}")
            else:
                print(f"Link already exists: {link}")