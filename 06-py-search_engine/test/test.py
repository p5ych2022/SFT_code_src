import requests
from bs4 import BeautifulSoup
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID, STORED
from whoosh.qparser import QueryParser
from whoosh.analysis import StemmingAnalyzer
from urllib.parse import urljoin, urlparse
import os
import threading
import queue
import time


class SearchEngine:
    def __init__(self, index_dir="search_index"):
        self.index_dir = index_dir
        self.url_queue = queue.Queue()
        self.crawled_urls = set()
        self.lock = threading.Lock()

        # Define schema for the search index
        self.schema = Schema(
            url=ID(stored=True),
            title=TEXT(stored=True),
            content=TEXT(analyzer=StemmingAnalyzer(), stored=True),
            description=STORED
        )

        # Create or open index
        if not os.path.exists(index_dir):
            os.makedirs(index_dir)
            self.ix = create_in(index_dir, self.schema)
        else:
            self.ix = open_dir(index_dir)

    def crawl_page(self, url):
        """Crawl a single page and extract information."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract title
                title = soup.title.string if soup.title else ""

                # Extract content
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                content = soup.get_text(separator=' ', strip=True)

                # Extract meta description
                meta_desc = ""
                meta_tag = soup.find('meta', attrs={'name': 'description'})
                if meta_tag:
                    meta_desc = meta_tag.get('content', '')

                # Extract links for further crawling
                links = []
                for link in soup.find_all('a'):
                    href = link.get('href')
                    if href:
                        absolute_url = urljoin(url, href)
                        if self._is_valid_url(absolute_url):
                            links.append(absolute_url)

                return {
                    'url': url,
                    'title': title,
                    'content': content,
                    'description': meta_desc,
                    'links': links
                }
            return None
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            return None

    def _is_valid_url(self, url):
        """Check if URL is valid and should be crawled."""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and parsed.scheme in ['http', 'https'])
        except:
            return False

    def index_page(self, page_data):
        """Index a single page."""
        if not page_data:
            return

        try:
            writer = self.ix.writer()
            writer.add_document(
                url=page_data['url'],
                title=page_data['title'],
                content=page_data['content'],
                description=page_data['description']
            )
            writer.commit()
        except Exception as e:
            print(f"Error indexing {page_data['url']}: {e}")

    def crawl_and_index(self, start_url, max_pages=100):
        """Crawl pages starting from start_url and index them."""
        self.url_queue.put(start_url)

        while not self.url_queue.empty() and len(self.crawled_urls) < max_pages:
            current_url = self.url_queue.get()

            with self.lock:
                if current_url in self.crawled_urls:
                    continue
                self.crawled_urls.add(current_url)

            print(f"Crawling: {current_url}")
            page_data = self.crawl_page(current_url)

            if page_data:
                self.index_page(page_data)
                # Add new URLs to queue
                for link in page_data['links']:
                    if link not in self.crawled_urls:
                        self.url_queue.put(link)

            # Be polite and don't hammer the server
            time.sleep(1)

    def search(self, query, limit=10):
        """Search the index for the given query."""
        try:
            with self.ix.searcher() as searcher:
                parser = QueryParser("content", self.ix.schema)
                query = parser.parse(query)
                results = searcher.search(query, limit=limit)

                search_results = []
                for result in results:
                    search_results.append({
                        'url': result['url'],
                        'title': result['title'],
                        'description': result['description'],
                        'score': result.score
                    })

                return search_results
        except Exception as e:
            print(f"Error searching: {e}")
            return []


def main():
    # Initialize search engine
    search_engine = SearchEngine()

    while True:
        print("\n1. Crawl and index new pages")
        print("2. Search")
        print("3. Exit")
        choice = input("Enter your choice (1-3): ")

        if choice == '1':
            start_url = input("Enter the starting URL to crawl: ")
            max_pages = int(input("Enter maximum number of pages to crawl: "))
            search_engine.crawl_and_index(start_url, max_pages)
            print("Crawling and indexing completed!")

        elif choice == '2':
            query = input("Enter your search query: ")
            results = search_engine.search(query)

            if results:
                print("\nSearch Results:")
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. {result['title']}")
                    print(f"URL: {result['url']}")
                    print(f"Description: {result['description'][:200]}...")
                    print(f"Relevance Score: {result['score']:.2f}")
            else:
                print("No results found.")

        elif choice == '3':
            print("Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()
