from bs4 import BeautifulSoup
from fastapi import HTTPException,Response
import httpx
import requests
import re
import urllib.parse



def fetch_movie_list(movie_name: str,response:Response): 
    """Fetch movie list from TMDB and return it."""
    url = f"https://www.themoviedb.org/search/movie?query={movie_name}&language=en-GB"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Request to TMDB timed out")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error fetching movie list: {str(e)}")

    soup = BeautifulSoup(response.text, 'html.parser')
    movies = []

    for card in soup.select('div.card.v4.tight'):
        movie_link = card.select_one('a.result')
        if not movie_link:
            continue
        href = movie_link['href']
        
        # Skip TV shows
        if href.startswith("/tv/"):
            continue


        movie_url = f"https://www.themoviedb.org{href}"

        movies.append({
            "title": card.select_one('h2').get_text(strip=True) if card.select_one('h2') else "Unknown",
            "poster": card.select_one('img')['src'] if card.select_one('img') else "No poster available",
            "release_date": card.select_one('span.release_date').get_text(strip=True) if card.select_one('span.release_date') else "Unknown",
            "overview": card.select_one('div.overview p').get_text(strip=True) if card.select_one('div.overview p') else "Overview not available",
            "url": movie_url,
        })

    return movies  # Return the fetched movies


def get_movie_details(movie_url):
    """Extract detailed movie information with JSON error handling."""
    try:
        response = requests.get(movie_url, timeout=10)
        response.raise_for_status()
    except requests.Timeout:
        return {"error": "Request to TMDB timed out"}
    except requests.RequestException as e:
        return {"error": f"Error fetching movie details: {str(e)}"}

    soup = BeautifulSoup(response.text, 'html.parser')

    director = next(
        (profile.select_one('a').get_text(strip=True)
         for profile in soup.select('li.profile')
         if profile.select_one('p.character') and 'Director' in profile.select_one('p.character').text),
        None
    )

    if not director:
        return {
            "director": None, "cast": [], "genres": [],
            "runtime": "Unknown", "certificate": "Unknown",
            "language": "Unknown", "watch_link": "No watch link available",
            "backdrops": []
        }

    cast = [
        (card.select_one('p').get_text(strip=True), card.select_one('img')['src'] if card.select_one('img') else "No Image")
        for card in soup.select('li.card')
    ]

    genres = [genre.get_text(strip=True) for genre in soup.select('span.genres a')]

    facts_section = soup.select_one('div.facts')
    runtime = facts_section.select_one('span.runtime').get_text(strip=True) if facts_section and facts_section.select_one('span.runtime') else "Unknown"
    certificate = facts_section.select_one('span.certification').get_text(strip=True) if facts_section and facts_section.select_one('span.certification') else "Unknown"

    language = next(
        (tag.find_parent().get_text(strip=True).replace("Original Language", "").strip()
         for tag in soup.find_all('strong', string=re.compile(r'Original Language', re.IGNORECASE))),
        "Unknown"
    )

    watch_link_element = soup.select_one('a[href*="/watch"]')
    streaming_url = f"https://www.themoviedb.org{watch_link_element['href']}" if watch_link_element else "No watch link available"
    watch_links = fetch_watch_links(streaming_url) if watch_link_element else ["No watch links available"]

    backdrops = fetch_backdrop_images(movie_url)
    overview_element = soup.select_one('div.overview p')
    overview = overview_element.get_text(strip=True) if overview_element else "No overview available"

    return {
        "director": director,
        "cast": cast,
        "genres": genres,
        "runtime": runtime,
        "certificate": certificate,
        "language": language,
        "watch_link": watch_links,
        "backdrops": backdrops,
        "overview": overview 
    }


def fetch_backdrop_images(movie_url):
    """Fetch backdrop images from TMDB movie image gallery with JSON error handling."""
    backdrop_url = movie_url.replace("?language=en-GB", "") + "/images/backdrops?language=en-GB"

    try:
        response = requests.get(backdrop_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        images = set(a['href'] for a in soup.select('a[title="View Original"]'))

        return list(images) if images else ["No backdrop images available"]

    except requests.RequestException as e:
        print(f"Error fetching backdrop images: {e}")
        return {"error": "Failed to fetch backdrop images"}


def fetch_watch_links(streaming_url):
    """Fetch streaming platform links from TMDB with JSON error handling."""
    try:
        response = requests.get(streaming_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        stream_section = soup.find('h3', string=re.compile(r'Stream', re.IGNORECASE))
        if not stream_section:
            return ["No watch links available"]

        watch_links = []
        for link in stream_section.find_next('ul', class_='providers').find_all('a', href=True):
            match = re.search(r'r=(https%3A%2F%2F[^\&]+)', link['href'])
            icon = link.find('img')['src'] if link.find('img') else None
            if match and icon:
                clean_url = urllib.parse.unquote(match.group(1))
                if not any(item['url'] == clean_url for item in watch_links):
                    watch_links.append({'icon': icon, 'url': clean_url})

        return watch_links if watch_links else ["No watch links available"]

    except requests.RequestException as e:
        print(f"Error fetching watch links: {e}")
        return {"error": "Failed to fetch watch links"}


async def fetch_movies_from_page(client, page, base_url):
    """Fetch movies from a single page asynchronously, with exception handling."""
    url = f"{base_url}?page={page}&language=en-GB"
    
    try:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Error fetching page {page}: {e}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request error: {e}")
    
    soup = BeautifulSoup(response.text, "html.parser")

    movies = []
    for card in soup.select("div.card.style_1"):
        title = card.select_one("h2").get_text(strip=True) if card.select_one("h2") else "Unknown"
        release_date = card.select_one("div.content p").text if card.select_one("div.content p") else "Unknown"
        poster = card.select_one("img")["src"] if card.select_one("img") else "No poster available"
        movie_link = card.select_one("a")["href"] if card.select_one("a") else None
        movie_url = f"https://www.themoviedb.org{movie_link}" if movie_link else "No URL available"

        movies.append({
            "title": title,
            "release_date": release_date,
            "poster": poster,
            "url": movie_url
        })

    return movies
