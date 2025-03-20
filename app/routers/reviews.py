from datetime import datetime
from fastapi import APIRouter,status,HTTPException,Depends
from ..schemas import ReviewCreateModel,ReviewResponseModel,ReviewEditModel,ReviewItemResponseModel
from ..OAuth2 import get_current_user
from ..models import Review,ReviewItem


router=APIRouter(prefix="/review",tags=['review'])

@router.post("/addReview", status_code=status.HTTP_201_CREATED)
async def add_review(review: ReviewCreateModel, user=Depends(get_current_user)):
    try:
        # Check if a movie exists with a review by the same user
        existing_movie = await Review.find_one(
            (Review.movie_name == review.movie_name) & 
            (Review.reviews.created_by.id == user.id)
        )

        if existing_movie:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already submitted a review for this movie."
            )

        # Fetch the movie without checking for user review (we already checked above)
        movie = await Review.find_one(Review.movie_name == review.movie_name)

        new_review = ReviewItem(
            review_content=review.review_content,
            rating=review.rating,
            created_by=user,  # Store user object
        )

        if movie:
            # Append the new review
            movie.reviews.append(new_review)

            # Calculate and update overall rating
            total_ratings = sum(r.rating for r in movie.reviews)
            movie.overall_rating = total_ratings / len(movie.reviews)

            # Save updated movie document
            await movie.save()
            overall_rating = movie.overall_rating
        else:
            # If the movie doesn't exist, create a new entry
            new_movie = Review(
                movie_name=review.movie_name,
                release_date=review.release_date,
                overall_rating=review.rating,  # First review, so use its rating
                reviews=[new_review],
            )

            await new_movie.insert()
            overall_rating = new_movie.overall_rating

        return {
            "Success": "Review added successfully",
            "overall_rating": round(overall_rating, 2)
        }

    except Exception as e:
        error = f"Review adding failed: {str(e)}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error)


@router.put("/editReview/{movie_name}", status_code=status.HTTP_200_OK)
async def edit_review(movie_name: str, review_update: ReviewEditModel, user=Depends(get_current_user)):
    """Allow a user to edit their existing review for a movie."""
    try:
        # Find the movie where the user has already submitted a review
        existing_movie = await Review.find_one(
            (Review.movie_name == movie_name) & 
            (Review.reviews.created_by.id == user.id)
        )

        if not existing_movie:
            raise HTTPException(status_code=404, detail="Either the movie does not exist or you haven't reviewed it.")

        # Use Beanie's `update` method to modify the user's review directly
        update_query = {
            "reviews.$.review_content": review_update.review_content,
            "reviews.$.rating": review_update.rating
        }

        updated_movie = await Review.find_one_and_update(
            {"movie_name": movie_name, "reviews.created_by.id": user.id},
            {"$set": update_query},
            return_document=True
        )

        if not updated_movie:
            raise HTTPException(status_code=500, detail="Failed to update the review.")

        # Recalculate the overall rating
        total_ratings = sum(rev.rating for rev in updated_movie.reviews)
        updated_movie.overall_rating = round(total_ratings / len(updated_movie.reviews), 2)

        # Save updated rating
        await updated_movie.save()

        return {
            "movie_name": movie_name,
            "updated_review_content": review_update.review_content,
            "overall_rating": updated_movie.overall_rating
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Review update failed: {str(e)}")

@router.delete("/deleteReview/{movie_name}", status_code=status.HTTP_200_OK)
async def delete_review(movie_name: str, user=Depends(get_current_user)):
    try:
        existing_movie = await Review.find_one(Review.movie_name == movie_name)
        if not existing_movie:
            raise HTTPException(status_code=404, detail="Movie not found")

        # Find the user's review
        user_review = None
        for review in existing_movie.reviews:
            if review.created_by.id == user.id:
                user_review = review
                break

        if not user_review:
            raise HTTPException(
                status_code=404, detail="User has not reviewed this movie"
            )

        # Remove the user's review
        existing_movie.reviews.remove(user_review)

        # If no reviews left, delete the movie
        if not existing_movie.reviews:
            await existing_movie.delete()
            return {"message": "Review and movie deleted successfully"}

        # Recalculate overall rating
        total_ratings = sum(rev.rating for rev in existing_movie.reviews)
        existing_movie.overall_rating = round(total_ratings / len(existing_movie.reviews), 2)

        await existing_movie.save()
        return {
            "message": "Review deleted successfully",
            "overall_rating": existing_movie.overall_rating
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete review: {str(e)}"
        )
from fastapi import Response
from ..schemas import ReviewResponseModel  # Import the schema

@router.get("/getReviews/{movie_name}", response_model=ReviewResponseModel, status_code=status.HTTP_200_OK)
async def get_reviews(movie_name: str):
    try:
        existing_movie = await Review.find_one(Review.movie_name == movie_name)
        if not existing_movie:
            raise HTTPException(status_code=404, detail="Movie not found")

        overall_rating = (
            round(sum(rev.rating for rev in existing_movie.reviews) / len(existing_movie.reviews), 2)
            if existing_movie.reviews else 0
        )

        return ReviewResponseModel(
            movie_name=existing_movie.movie_name,
            release_date=existing_movie.release_date,
            overall_rating=overall_rating,
            reviews=[
                ReviewItemResponseModel(
                    review_content=rev.review_content,
                    rating=rev.rating,
                    created_by=rev.created_by.id,
                    created_at=rev.created_at
                )
                for rev in existing_movie.reviews
            ],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get reviews: {str(e)}")
