import asyncio
from bs4 import BeautifulSoup
from fastapi import HTTPException,Response
import requests
import re
import urllib.parse

import yt_dlp

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

        movie_url = f"https://www.themoviedb.org{movie_link['href']}"

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

    return {
        "director": director,
        "cast": cast,
        "genres": genres,
        "runtime": runtime,
        "certificate": certificate,
        "language": language,
        "watch_link": watch_links,
        "backdrops": backdrops
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



async def fetch_trailer_url(movie_name: str):
    """Fetch trailer URL asynchronously."""
    search_query = f"{movie_name} official trailer"

    ydl_opts = {
        "quiet": True,
        "default_search": "ytsearch1",
        "noplaylist": True,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "timeout": 15,  # Reduced timeout
        "cookies-from-browser": "chrome"
    }

    loop = asyncio.get_running_loop()
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, ydl.extract_info, search_query, False)

            if "entries" in info and info["entries"]:
                return info["entries"][0].get("webpage_url", "Trailer not found.")

    except Exception as e:
        return f"Error fetching trailer: {str(e)}"