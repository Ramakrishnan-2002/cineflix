from typing import List
from fastapi.responses import JSONResponse, ORJSONResponse
import httpx
import requests
from fastapi import APIRouter, HTTPException, Response, Depends
from googleapiclient.discovery import build
from ..scraper import fetch_movie_list, get_movie_details
from ..schemas import MovieBasic, MovieDetails
from ..OAuth2 import get_current_user
from ..config import settings

router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("/search/{movie_name}", response_model=List[MovieBasic])
def search_movies(movie_name: str, response: Response, user=Depends(get_current_user)):
    """Fetch and return movie list synchronously."""
    movies = fetch_movie_list(movie_name, response)
    if not movies:
        response.status_code = 404
        return ORJSONResponse({"detail": f"No movies found for '{movie_name}'"})

    return ORJSONResponse(movies)


@router.get("/details/", response_model=List[MovieDetails])
def get_movie_full_details(movie_url: str, user=Depends(get_current_user)):
    """Fetch and return detailed movie data synchronously with JSON error handling."""
    
    if not movie_url.startswith("https://www.themoviedb.org/movie/"):
        return JSONResponse(content={"error": "Invalid movie URL"}, status_code=400)

    try:
        details = get_movie_details(movie_url)
        movies = MovieDetails(**details)

        return ORJSONResponse(content=movies.model_dump(), status_code=200)

    except HTTPException as e:
        return JSONResponse(content={"error": e.detail}, status_code=e.status_code)

    except requests.Timeout:
        return JSONResponse(content={"error": "Request to TMDB timed out"}, status_code=504)

    except requests.RequestException as e:
        return JSONResponse(content={"error": "Error fetching movie details", "details": str(e)}, status_code=502)

    except Exception as e:
        return JSONResponse(content={"error": "Internal Server Error", "details": str(e)}, status_code=500)







async def get_trailer_from_youtube(movie_name: str):
    """Fetch the first YouTube search result for the movie trailer using YouTube API asynchronously."""
    search_query = f"{movie_name} official trailer"

    params = {
        "q": search_query,
        "part": "snippet",
        "maxResults": 1,
        "type": "video",
        "key": settings.YOUTUBE_API_KEY,  # Ensure this is valid
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(settings.YOUTUBE_API_URL, params=params)
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="YouTube API request failed")

        data = response.json()  # JSON conversion

        if "items" in data and data["items"]:
            video_id = data["items"][0]["id"]["videoId"]
            return f"https://www.youtube.com/watch?v={video_id}"

    return None

@router.get("/trailer/{movie_name}")
async def get_movie_trailer(movie_name: str, user=Depends(get_current_user)):
    """Fetch the movie trailer URL using YouTube API."""
    trailer_url = await get_trailer_from_youtube(movie_name)

    if trailer_url:
        return {"movie_name": movie_name, "trailer_url": trailer_url}
    
    raise HTTPException(status_code=404, detail="Trailer not found.")