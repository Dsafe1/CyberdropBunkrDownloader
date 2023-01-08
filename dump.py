import requests
import json
import argparse
import sys
import os
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse 
def get_items_list(url, extensions, min_file_size, use_album_id, only_export, custom_path=None, ignore_error=False):

    extensions_list = extensions.split(',') if extensions is not None else []
    hostname = get_url_data(url)['hostname']
       
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"HTTP error {r.status_code}")

    soup = BeautifulSoup(r.content, 'html.parser')
    if hostname in ['bunkr.is', 'stream.bunkr.is', 'bunkr.ru', 'stream.bunkr.ru']:
        check_bunkr_status(ignore_error);
        item_urls = []
        album_or_file = 'file' if hostname in ['stream.bunkr.is', 'stream.bunkr.ru'] else 'album'
        json_data_element = soup.find("script", {"id": "__NEXT_DATA__"})
        json_data = json.loads(json_data_element.string)
        if len(json_data['props']['pageProps']) == 0:
            raise Exception("[-] Failed to load the album/file, maybe try visiting the album in a browser?")

        files = json_data['props']['pageProps']['album']['files'] if album_or_file == 'album' else [json_data['props']['pageProps']['file']]
        if album_or_file == 'file':
            item_urls = [f"{file['mediafiles']}/{file['name']}" for file in files if int(file['size']) > (min_file_size * 1000)]
        else:
            item_urls = [f"{file['cdn'].replace('/cdn','/media-files')}/{file['name']}" for file in files if int(file['size']) > (min_file_size * 1000)]
        album_name = remove_illegal_chars(json_data['props']['pageProps'][album_or_file]['name']) if not use_album_id else str(json_data['props']['pageProps'][album_or_file]['id'])
    else:
        items = soup.find_all('a', {'class': 'image'})
        item_urls = [item['href'] for item in items]
        album_name = remove_illegal_chars(soup.find('h1', {'id': 'title'}).text)

    download_path = get_and_prepare_download_path(custom_path, album_name)
    already_downloaded_url = get_already_downloaded_url(download_path)
    if not only_export:
        for item_url in item_urls:
            extension = get_url_data(item_url)['extension']
            if ((extension in extensions_list or len(extensions_list) == 0) and (item_url not in already_downloaded_url)):
                print(f"[+] Downloading {item_url}")
                
                download(item_url, download_path, hostname in ['bunkr.ru', 'bunkr.is'])
    else:
        export_list(item_urls, download_path)
        return

def download(item_url, download_path, is_bunkr=False):

    file_name = get_url_data(item_url)['file_name']
    with requests.get(item_url, headers={'Referer': 'https://stream.bunkr.ru/', 'User-Agent': 'Mozila/5.0'} if is_bunkr else {}, stream=True) as r:
        if r.url in ["https://static.bunkr.ru/v/maintenance.mp4", "https://static.bunkr.is/v/maintenance.mp4"]:
            print(f"[-] Error Downloading \"{file_name}\", server is under maintenance!")
            return
        with open(os.path.join(download_path, file_name), 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    mark_as_downloaded(item_url, download_path)

    return

def get_url_data(url):
    parsed_url = urlparse(url)
    return {'file_name': os.path.basename(parsed_url.path), 'extension': os.path.splitext(parsed_url.path)[1], 'hostname': parsed_url.hostname}

def get_and_prepare_download_path(custom_path, album_name):

    final_path = 'downloads' if custom_path is None else os.path.join(custom_path, 'downloads')
    final_path = os.path.join(final_path, album_name) if album_name is not None else 'downloads'
    final_path = final_path.replace('\n', '')

    if not os.path.isdir(final_path):
        os.makedirs(final_path)

    already_downloaded_path = os.path.join(final_path, 'already_downloaded.txt')
    if not os.path.isfile(already_downloaded_path):
        with open(already_downloaded_path, 'x', encoding='utf-8'):
            pass

    return final_path

def export_list(item_urls, download_path):

    list_path = os.path.join(download_path, 'url_list.txt')

    with open(list_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(item_urls))

    print(f"[+] File list exported in {list_path}")

    return

def get_already_downloaded_url(download_path):

    file_path = os.path.join(download_path, 'already_downloaded.txt')

    if not os.path.isfile(file_path):
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read().splitlines()

def mark_as_downloaded(item_url, download_path):

    file_path = os.path.join(download_path, 'already_downloaded.txt')
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f"{item_url}\n")

    return

def check_bunkr_status(ignore=False):
    print("Checking bunkr statuses...")
    r = requests.get("https://status.bunkr.ru/")
    if r.status_code != 200:
        raise Exception(f"HTTP error {r.status_code}")
    soup = BeautifulSoup(r.content, 'html.parser')
    els = soup.find_all("div", {"class": "column"})
    for el in els:
        childrenList = list(el.children)
        server = childrenList[1].text
        status = childrenList[3].text
        print(f"{server}: {status}")
        if status not in ["Operational", "Degraded performance"]:
            print("\n")
            print(f"{server} Seems to not be operational! videos that are downloaded from that server will be broken", end="", flush=True)
            if ignore == False:
                print(", if you want to ignore this error run the script again with the argument \"-ignore\"")
                exit(1)
            else:
                print("\n")
    return    

def remove_illegal_chars(string):
    return re.sub(r"[<>:/\\|?*\"]|[\0-\31]", "-", string)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(sys.argv[1:])
    parser.add_argument("-u", help="Url to fetch", type=str, required=True)
    parser.add_argument("-e", help="Extensions to download (comma separated)", type=str)
    parser.add_argument("-s", help="Minimum file size to download (in kilobytes, only for Bunkr)", type=int, const=0, default=0, nargs='?')
    parser.add_argument("-i", help="Use album id instead of album name for the folder name (only for Bunkr)", action="store_true")
    parser.add_argument("-p", help="Path to custom downloads folder")
    parser.add_argument("-w", help="Export url list (ex: for wget)", action="store_true")
    parser.add_argument("-ignore", help="Ignores if servers were down",action="store_true")

    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    get_items_list(args.u, args.e, args.s, args.i, args.w, args.p, args.ignore)
