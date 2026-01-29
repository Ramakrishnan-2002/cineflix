import asyncio
from typing import List
from fastapi.responses import  ORJSONResponse
import httpx
import requests
from fastapi import APIRouter, HTTPException, Response, Depends,status
from ..scraper import fetch_movie_list, get_movie_details,fetch_movies_from_page
from ..schemas import MovieBasic, MovieDetails
from ..OAuth2 import get_current_user
from ..config import settings

router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("/search/{movie_name}", response_model=List[MovieBasic])
def search_movies(movie_name: str, response: Response, user=Depends(get_current_user)):
    movies = fetch_movie_list(movie_name, response)
    if not movies:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail= f"No movies found for '{movie_name}'")

    return ORJSONResponse(movies)


@router.get("/details/", response_model=List[MovieDetails])
def get_movie_full_details(movie_url: str, user=Depends(get_current_user)):
    
    if not movie_url.startswith("https://www.themoviedb.org/movie/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid movie URL")

    try:
        details = get_movie_details(movie_url)
        movies = MovieDetails(**details)
        return ORJSONResponse(content=movies.model_dump(), status_code=200)

    except requests.Timeout:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request to TMDB timed out")

    except requests.RequestException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Error fetching movie details: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error: {str(e)}")






async def get_trailer_from_youtube(movie_name: str):
    search_query = f"{movie_name} official trailer"

    params = {
        "q": search_query,
        "part": "snippet",
        "maxResults": 1,
        "type": "video",
        "key": settings.YOUTUBE_API_KEY,  
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(settings.YOUTUBE_API_URL, params=params)
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="YouTube API request failed")

        data = response.json() 

        if "items" in data and data["items"]:
            video_id = data["items"][0]["id"]["videoId"]
            return f"https://www.youtube.com/watch?v={video_id}"

    return None

@router.get("/trailer/{movie_name}")
async def get_movie_trailer(movie_name: str, user=Depends(get_current_user)):
   
    trailer_url = await get_trailer_from_youtube(movie_name)

    if trailer_url:
        return {"movie_name": movie_name, "trailer_url": trailer_url}
    
    raise HTTPException(status_code=404, detail="Trailer not found.")


POPULAR_URL = "https://www.themoviedb.org/movie"
TOP_RATED_URL = "https://www.themoviedb.org/movie/top-rated"
UPCOMING_URL = "https://www.themoviedb.org/movie/upcoming"
MAX_PAGES = 10 

async def fetch_all_movies_by_category(base_url):

    try:
        async with httpx.AsyncClient() as client:
            tasks = [fetch_movies_from_page(client, page, base_url) for page in range(1, MAX_PAGES + 1)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_movies = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Skipping failed request: {result}")  
                continue
            all_movies.extend(result)

        if not all_movies:
            raise HTTPException(status_code=404, detail="No movies found")

        return {"movies": all_movies}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

@router.get("/popular")
async def fetch_popular_movies(user=Depends(get_current_user)):
    return await fetch_all_movies_by_category(POPULAR_URL)

@router.get("/top-rated")
async def fetch_top_rated_movies(user=Depends(get_current_user)):
    return await fetch_all_movies_by_category(TOP_RATED_URL)

@router.get("/upcoming")
async def fetch_upcoming_movies(user=Depends(get_current_user)):
    return await fetch_all_movies_by_category(UPCOMING_URL)
