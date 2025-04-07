import requests
from bs4 import BeautifulSoup
import os
from collections import deque
from urllib.parse import urljoin, urlparse


def crawl_pages(start_url, max_pages):
    """
    Crawl web pages using Breadth-First Search (BFS) starting from a given URL.
    It collects text from up to 'max_pages' distinct pages.
    Returns a dictionary {url: [list_of_text_lines]} for each crawled page.
    """
    if max_pages <= 0:
        return {}

    visited = set()
    queue = deque([start_url])
    pages_crawled = 0
    url_text_map = {}  # Store {url: [list_of_lines]}

    while queue and pages_crawled < max_pages:
        current_url = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        try:
            response = requests.get(current_url, timeout=10)
            # Only proceed if the page is successfully retrieved
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract all visible text from the page and split it by lines
                text_content = soup.get_text(separator='\n', strip=True)
                lines = text_content.split('\n')
                url_text_map[current_url] = lines
                pages_crawled += 1

                # Extract all <a href=""> links and enqueue new URLs
                for link in soup.find_all('a', href=True):
                    absolute_link = urljoin(current_url, link['href'])
                    parsed = urlparse(absolute_link)
                    # Only allow HTTP(S) URLs and avoid revisiting
                    if parsed.scheme in ('http', 'https') and absolute_link not in visited:
                        queue.append(absolute_link)

        except Exception as e:
            print(f"Error while crawling {current_url}: {e}")

    print(f"Crawling complete. {pages_crawled} pages fetched.")
    return url_text_map


def search_keyword(url_text_map, keyword):
    """
    Search for the specified keyword within the content of crawled pages.
    Returns a list of tuples: (url, [matched_lines]) for each matching page.
    """
    results = []
    for url, lines in url_text_map.items():
        matched_lines = []
        # Search for the keyword in each line
        for line in lines:
            if keyword in line:
                matched_lines.append(line.strip())
        if matched_lines:
            results.append((url, matched_lines))
    return results


def write_results_to_file(keyword, search_results):
    """
    Write the search results to a file in 'result/{keyword}.txt'.
    Each result includes the URL and the matching lines (as proof).
    """
    # Ensure the 'result/' directory exists
    os.makedirs('result', exist_ok=True)
    output_file = os.path.join('result', f"{keyword}.txt")

    with open(output_file, 'w', encoding='utf-8') as f:
        for url, lines in search_results:
            f.write(f"=== Found in URL: {url} ===\n")
            for line in lines:
                f.write(f"Prove: {line}\n")
            f.write("\n")
    print(f"Search results written to: {output_file}")


def main():
    # Prompt user to enter the initial URL
    start_url = input("Enter the starting URL to crawl: ").strip()
    if not start_url:
        print("Invalid URL. Exiting.")
        return

    # Prompt user to input max number of pages to crawl (0-100)
    max_pages_input = input("Enter number of pages to crawl (0-100): ").strip()
    try:
        max_pages = int(max_pages_input)
    except ValueError:
        max_pages = 0  # Default to 0 if not a valid number

    # Clamp the range to [0, 100]
    max_pages = max(0, min(100, max_pages))

    # Begin crawling
    url_text_map = crawl_pages(start_url, max_pages)

    # Prompt user to input the keyword to search for
    keyword = input("Enter the keyword to search for: ").strip()
    if not keyword:
        print("Invalid keyword. Exiting.")
        return

    # Perform keyword search
    search_results = search_keyword(url_text_map, keyword)

    # Display search results in console
    if not search_results:
        print("No pages contain the given keyword.")
    else:
        for url, lines in search_results:
            print(f"[URL]: {url}")
            for line in lines:
                print(f"Prove: {line}")
            print("-" * 40)

    # Write results to file
    write_results_to_file(keyword, search_results)


if __name__ == "__main__":
    main()