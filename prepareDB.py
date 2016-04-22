import queue
import pymongo
import time
from DataService import Mongo
from movieRecommend import MovieRecommend
from movieRecommend import Candidate
import movieLensParser
import anewParser

def prepare_genres(mongo):
    print("[prepare_genres] Starting pepare genres list...")
    startTime = time.time()

    genres_dict = {}
    cursor = mongo.db["movie"].find({})
    for cur_movie in cursor:
        cur_mid = cur_movie["mid"]
        cur_genres = cur_movie["genres"]
        copy_movie = {}
        copy_movie["mid"] = cur_movie["mid"]
        copy_movie["imdb_rating"] = cur_movie["imdb_rating"]
        copy_movie["imdb_votes"] = cur_movie["imdb_votes"]
        for genre in cur_genres:
            if genre not in genres_dict:
                cur_list = []
            else:
                cur_list = genres_dict[genre]
            cur_list.append(copy_movie)
            genres_dict[genre] = cur_list

    for genre, movies in genres_dict.items():
        mongo.db["genres_list"].update_one({"genre": genre}, {"$set": {
            "relevant_movie": movies,
            "popular": len(movies)
            }}, True)
        # print(genre + " " + str(len(movies)))

    mongo.db["genres_list"].create_index([("genre", pymongo.ASCENDING)])
    print("[prepare_genres] Created index for genre in genres_list")
    print("[prepare_genres] Done (%0.2fs)." % (time.time() - startTime))

def prepare_actors(mongo):
    print("[prepare_actors] Starting pepare actors list...")
    startTime = time.time()

    actors_dict = {}
    cursor = mongo.db["movie"].find({})
    for cur_movie in cursor:
        cur_mid = cur_movie["mid"]
        cur_actors = cur_movie["actors"]
        copy_movie = {}
        copy_movie["mid"] = cur_movie["mid"]
        copy_movie["imdb_rating"] = cur_movie["imdb_rating"]
        copy_movie["imdb_votes"] = cur_movie["imdb_votes"]
        for actor in cur_actors:
            if actor not in actors_dict:
                cur_list = []
            else:
                cur_list = actors_dict[actor]
            cur_list.append(copy_movie)
            actors_dict[actor] = cur_list

    progressInterval = 3000    # How often should we print a progress report to the console?
    progressTotal = 55740      # Approximate number of total actors.
    bulkSize = 2000            # How many documents should we store in memory before inserting them into the database in bulk?
    bulkPayload = pymongo.bulk.BulkOperationBuilder(mongo.db["actors_list"], ordered = False)
    count = 0
    skipCount = 0
    for actor, movies in actors_dict.items():
        count += 1
        if count % progressInterval == 0:
            print("[prepare_actors] %5d actors processed so far. (%d%%) (%0.2fs)" % (count, int(count * 100 / progressTotal), time.time() - startTime))

        bulkPayload.find({"actor": actor}).update({"$set": {
            "relevant_movie": movies,
            "popular": len(movies)
            }})

        if count % bulkSize == 0:
            try:
                bulkPayload.execute()
            except pymongo.errors.OperationFailure as e:
                skipCount += len(e.details["writeErrors"])
            bulkPayload = pymongo.bulk.BulkOperationBuilder(mongo.db["actors_list"], ordered = False)

    if count % bulkSize > 0:
        try:
            bulkPayload.execute()
        except pymongo.errors.OperationFailure as e:
            skipCount += len(e.details["writeErrors"])

    mongo.db["actors_list"].create_index([("actor", pymongo.ASCENDING)])
    print("[prepare_actors] Created index for actor in actors_list")
    print("[prepare_actors] Skipped " + str(skipCount) + " insertions.")
    print("[prepare_actors] Done (%0.2fs)." % (time.time() - startTime))

def prepare_rankings_movies_all(mongo):
    # top rated movies among all
    # most popular movies among all
    print("[prepare_rankings_movies_all] Starting pepare ranking...")

    top_rated_heap = queue.PriorityQueue()
    most_popular_heap = queue.PriorityQueue()
    cursor = mongo.db["movie"].find({})
    for cur_movie in cursor:
        cur_rating = cur_movie["imdb_rating"]
        if cur_rating != "N/A":
            top_rated_heap.put(Candidate(cur_movie["mid"], cur_rating))
            # maintain the size
            if top_rated_heap.qsize() > 100:
                top_rated_heap.get()
        cur_votes_string = cur_movie["imdb_votes"]
        if cur_votes_string != "N/A":
            cur_votes = int(cur_votes_string.replace(',', ''))
            most_popular_heap.put(Candidate(cur_movie["mid"], cur_votes))
            # maintain the size
            if most_popular_heap.qsize() > 100:
                most_popular_heap.get()

    top_rated = []
    while not top_rated_heap.empty():
        cur_candidate = top_rated_heap.get()
        top_rated.append(cur_candidate.cid)
    top_rated.reverse()

    most_popular = []
    while not most_popular_heap.empty():
        cur_candidate = most_popular_heap.get()
        most_popular.append(cur_candidate.cid)
    most_popular.reverse()

    mongo.db["genres_list"].update_one({"genre": "all"}, {"$set": {
        "top_rated": top_rated,
        "most_popular": most_popular
        }}, True)

    print("[prepare_rankings_movies_all] Done.")

def prepare_rankings_movies_genres(mongo):
    # top rated movies for each genres
    # most popular movies for each genres
    print("[prepare_rankings_movies_genres] Starting pepare ranking...")

    cursor = mongo.db["genres_list"].find({})
    for cur_genre in cursor:
        # skip the "all" genre
        if "relevant_movie" not in cur_genre:
            continue
        relevant_movies = cur_genre["relevant_movie"]
        top_rated_heap = queue.PriorityQueue()
        most_popular_heap = queue.PriorityQueue()
        for cur_movie in relevant_movies:
            cur_rating = cur_movie["imdb_rating"]
            if cur_rating != "N/A":
                top_rated_heap.put(Candidate(cur_movie["mid"], cur_rating))
                # maintain the size
                if top_rated_heap.qsize() > 30:
                    top_rated_heap.get()
            cur_votes_string = cur_movie["imdb_votes"]
            if cur_votes_string != "N/A":
                cur_votes = int(cur_votes_string.replace(',', ''))
                most_popular_heap.put(Candidate(cur_movie["mid"], cur_votes))
                # maintain the size
                if most_popular_heap.qsize() > 30:
                    most_popular_heap.get()

        top_rated = []
        while not top_rated_heap.empty():
            cur_candidate = top_rated_heap.get()
            top_rated.append(cur_candidate.cid)
        top_rated.reverse()

        most_popular = []
        while not most_popular_heap.empty():
            cur_candidate = most_popular_heap.get()
            most_popular.append(cur_candidate.cid)
        most_popular.reverse()

        mongo.db["genres_list"].update_one({"genre": cur_genre["genre"]}, {"$set": {
            "top_rated": top_rated,
            "most_popular": most_popular
            }}, True)

    print("[prepare_rankings_movies_genres] Done.")

def prepare_rankings_actor(mongo):
    # most popular actors
    print("[prepare_rankings_actor] Starting pepare ranking...")

    most_popular_heap = queue.PriorityQueue()
    cursor = mongo.db["actors_list"].find({})
    for cur_actor in cursor:
        if "popular" not in cur_actor:
            continue
        cur_popular = cur_actor["popular"]
        most_popular_heap.put(Candidate(cur_actor["actor"], cur_popular))
        # maintain the size
        if most_popular_heap.qsize() > 100:
            most_popular_heap.get()

    most_popular = []
    while not most_popular_heap.empty():
        cur_candidate = most_popular_heap.get()
        most_popular.append(cur_candidate.cid)
    most_popular.reverse()

    mongo.db["actors_list"].update_one({"actor": "all"}, {"$set": {
        "most_popular": most_popular
        }}, True)

    print("[prepare_rankings_actor] Done.")

def prepare_rankings(mongo):
    print("[prepare_rankings] Starting pepare ranking...")
    startTime = time.time()

    # top rated movies among all
    # most popular movies among all
    # runtime: 6~7s
    prepare_rankings_movies_all(mongo)

    # top rated movies for each genres
    # most popular movies for each genres
    # runtime: 2~3s
    prepare_rankings_movies_genres(mongo)

    # most popular actors
    # runtime: 1s
    prepare_rankings_actor(mongo)

    print("[prepare_rankings] Done (%0.2fs)." % (time.time() - startTime))

def prepare_recommend(mongo):
    print("[prepare_recommend] TODO")

def prepare():
    print("[prepareDB] Starting pepare database...")
    startTime = time.time()

    mongo = Mongo("movieRecommend")

    # Store MovieLens data into database.
    # runtime: (1~2hours)
    movieLensParser.parse(mongo)
    
    # Add ANEW all list into database.
    # runtime: (0.05s)
    anewParser.parse(mongo)

    # Pre-computation
    # all kinds of ranking
    prepare_genres(mongo)
    prepare_actors(mongo)
    prepare_rankings(mongo)

    # recommendations for all movies
    prepare_recommend(mongo)

    print("[prepareDB] Done (%0.2fs)." % (time.time() - startTime))


def main():
    prepare()

if __name__ == "__main__":
    main()