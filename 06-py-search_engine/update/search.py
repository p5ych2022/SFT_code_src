import time
import requests
from bs4 import BeautifulSoup
import os
from collections import deque
from urllib.parse import urljoin, urlparse

from whoosh.fields import Schema, ID, TEXT, STORED
from whoosh.index import create_in, open_dir
from whoosh.analysis import StemmingAnalyzer
from whoosh.qparser import QueryParser
import sys

sys.setrecursionlimit(200000)  # or some higher number


def creat_or_open_index(index_dir="search_index"):
    """
    Creates or opens a Whoosh index in the specified directory.

    Args:
        index_dir (str): The path to the directory that stores or will store the index.
            If the directory does not exist or is empty, a new index is created.
            Otherwise, the existing index is opened.

    Returns:
        whoosh.index.Index: A Whoosh index object ready for writing and searching.
    """
    schema = Schema(
        url=ID(stored=True, unique=True),
        title=TEXT(stored=True),
        content=TEXT(stored=True, analyzer=StemmingAnalyzer()),
        description=STORED
    )
    if not os.path.exists(index_dir) or not os.listdir(index_dir):
        os.makedirs(index_dir, exist_ok=True)
        ix = create_in(index_dir, schema)
    else:
        ix = open_dir(index_dir)
    return ix


def parse_page(url):
    """
    Fetches an HTML page from the given URL and extracts title, text content, meta description,
    and outbound links (HTTP/HTTPS only).

    Args:
        url (str): The web page URL to parse.

    Returns:
        dict or None:
            A dictionary containing 'url', 'title', 'content', 'description', and 'links' if
            the page is retrieved and parsed successfully, or None otherwise.
    """
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            page_title = soup.title.string if soup.title else ""
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            page_content = soup.get_text(separator='\n', strip=True)
            meta_desc = ""
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag:
                meta_desc = meta_tag.get('content', '')
            links = []
            for link in soup.find_all('a', href=True):
                absolute_link = urljoin(url, link['href'])
                parsed = urlparse(absolute_link)
                if parsed.scheme in ('http', 'https'):
                    links.append(absolute_link)
            return {
                'url': url,
                'title': page_title,
                'content': page_content,
                'description': meta_desc,
                'links': links
            }
        return None
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return None


def crawl_pages_and_index(start_url, max_pages, index_dir="search_index"):
    """
    Performs a BFS crawl starting from the specified URL, up to 'max_pages' pages,
    and writes all extracted data into a Whoosh index.

    Args:
        start_url (str): The initial URL to begin crawling.
        max_pages (int): The maximum number of pages to be crawled.
        index_dir (str): The directory where the Whoosh index is located or will be created.

    Returns:
        None: The function indexes the data and prints a summary, but returns nothing.
    """
    ix = creat_or_open_index(index_dir=index_dir)
    visited = set()
    queue = deque([start_url])
    pages_crawled = 0
    while queue and pages_crawled < max_pages:
        current_url = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)
        page_info = parse_page(current_url)
        if page_info:
            try:
                writer = ix.writer()
                writer.add_document(
                    url=page_info['url'],
                    title=str(page_info['title']),
                    content=page_info['content'][:100],
                    description=page_info['description']
                )
                writer.commit()

            except Exception as e:
                print(f"Error writing to index for {current_url}: {e}")
            finally:
                pages_crawled += 1
            for link in page_info['links']:
                if link not in visited:
                    queue.append(link)
        time.sleep(1)
    print(f"Crawling complete. {pages_crawled} pages indexed.")


def search_in_index(keyword, index_dir="search_index", limit=10):
    """
    Searches the created or existing Whoosh index for a given keyword and returns
    a list of matching documents, ranked by relevance.

    Args:
        keyword (str): The user-input search term.
        index_dir (str): The directory of the Whoosh index to be searched.
        limit (int): The maximum number of results to return.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary contains 'url',
        'title', 'description', and 'score' for a matching page.
        If an error occurs or no matches are found, an empty list is returned.
    """
    results_list = []
    try:
        ix = open_dir(index_dir)
        with ix.searcher() as searcher:
            parser = QueryParser("content", ix.schema)
            parsed_query = parser.parse(keyword)
            hits = searcher.search(parsed_query, limit=limit)
            for hit in hits:
                results_list.append({
                    'url': hit['url'],
                    'title': hit['title'],
                    'description': hit.get('description', ''),
                    'score': hit.score
                })
    except Exception as e:
        print(f"Error searching index: {e}")
        return []
    return results_list


def write_results_to_file(keyword, search_results):
    """
    Writes the search results to a file named '{keyword}.txt' in the 'result' directory.

    Args:
        keyword (str): The user-input search term, also used for the output filename.
        search_results (list[dict]): The list of matched documents, each containing URL,
            title, description, and relevance score.

    Returns:
        None: Writes the ranked results into a file and prints a confirmation message,
        but does not return any data.
    """
    os.makedirs('result', exist_ok=True)
    output_file = os.path.join('result', f"{keyword}.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        for idx, item in enumerate(search_results, start=1):
            f.write(f"[Rank #{idx} | Score: {item['score']:.2f}]\n")
            f.write(f"URL: {item['url']}\n")
            f.write(f"Title: {item['title']}\n")
            if item['description']:
                f.write(f"Meta Description: {item['description']}\n")
            f.write("\n")
    print(f"Search results written to: {output_file}")


def main():
    """
    Main entry point that orchestrates the entire process of crawling, indexing, and searching.
    1) Prompts the user to enter the starting URL and max pages (0-100).
    2) Crawls and indexes the content using BFS.
    3) Prompts the user for a keyword to search.
    4) Prints results and writes them to a file named '{keyword}.txt' in the 'result' folder.

    Args:
        None

    Returns:
        None
    """
    start_url = input("Enter the starting URL to crawl: ").strip()
    if not start_url:
        print("Invalid URL. Exiting.")
        return
    max_pages_input = input("Enter number of pages to crawl (0-100): ").strip()
    try:
        max_pages = int(max_pages_input)
    except ValueError:
        max_pages = 0
    max_pages = max(0, min(100, max_pages))
    crawl_pages_and_index(start_url, max_pages, index_dir="search_index")
    keyword = input("Enter the keyword to search for: ").strip()
    if not keyword:
        print("Invalid keyword. Exiting.")
        return
    results = search_in_index(keyword, index_dir="search_index", limit=10)
    if not results:
        print("No pages contain the given keyword.")
    else:
        for i, res in enumerate(results, start=1):
            print(f"[Rank #{i} | Score: {res['score']:.2f}]")
            print(f"URL: {res['url']}")
            print(f"Title: {res['title']}")
            if res['description']:
                print(f"Meta Description: {res['description']}")
            print("-" * 40)
    write_results_to_file(keyword, results)


if __name__ == "__main__":
    main()