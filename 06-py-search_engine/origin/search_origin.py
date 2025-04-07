import requests
import whoosh
from bs4 import BeautifulSoup
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT
from whoosh.qparser import QueryParser
import os


def crawl_and_index(url, index_dir):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            text_content = soup.get_text()

            if not os.path.exists(index_dir):
                os.mkdir(index_dir)

            schema = Schema(content=TEXT(stored=True))
            ix = create_in(index_dir, schema)
            writer = ix.writer()
            writer.add_document(content=text_content)
            writer.commit()
    except Exception as e:
        print(f"Error crawling and indexing: {e}")


def search_index(query, index_dir):
    try:
        ix = whoosh.index.open_dir(index_dir)
        with ix.searcher() as searcher:
            parser = QueryParser("content", ix.schema)
            parsed_query = parser.parse(query)
            results = searcher.search(parsed_query)
            relevant_results = []
            for result in results:
                relevant_results.append(result['content'])
            return relevant_results
    except Exception as e:
        print(f"Error searching index: {e}")
        return []


if __name__ == "__main__":
    url = "http://43.138.65.118:56666/simple"
    index_dir = "index"
    crawl_and_index(url, index_dir)
    user_query = input("Enter your search query: ")
    results = search_index(user_query, index_dir)
    if results:
        for i, result in enumerate(results, start=1):
            print(f"Result {i}: {result[:200]}...")
    else:
        print("No results found.")

