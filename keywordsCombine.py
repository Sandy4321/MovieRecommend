from DataService import Mongo
import pymongo
import time
from imdbMovieLensTags import imdbKeywords, imdbIgnore
import imdbPeopleIndex

def collect_from_keywords(client):
    db_imdb = client["imdb"]
    db_integration = client["integration"]

    count = 0
    progressInterval = 100            # How often should we print a progress report to the console?
    progressTotal = len(imdbKeywords) # Approximate number of total lines in the file.

    print("[keywordsCombine] Starting collection of keywords...")
    startTime = time.time()

    tags_to_movies = {}
    for key in imdbKeywords.keys():
        count += 1
        if count % progressInterval == 0:
            print("[keywordsCombine] %4d keys processed so far. (%d%%) (%0.2fs)" % (count, int(count * 100 / progressTotal), time.time() - startTime))

        # construct the ignored list
        filter_movies = set()
        if key in imdbIgnore.keys():
            for filter_key in imdbIgnore[key]:
               filter_cursor = db_imdb["movies"].find({"keywords": filter_key})
               for filter_movie in filter_cursor:
                    filter_movies.add(filter_movie["imdbtitle"])

        cursor = db_imdb["movies"].find({"keywords": key})
        for cur_movie in cursor:
            if cur_movie["imdbtitle"] in filter_movies or "tv" in cur_movie:
                continue
            for tag in imdbKeywords[key]:
                if tag not in tags_to_movies:
                    tags_to_movies[tag] = [cur_movie["imdbtitle"]]
                else:
                    tags_to_movies[tag].append(cur_movie["imdbtitle"])

    for tag in tags_to_movies.keys():
        db_integration["keywords"].update_one({"keyword": tag}, {"$set": {
            "relevant_movie": tags_to_movies[tag],
            "popularity": len(tags_to_movies[tag])
            }}, True)

    print("[keywordsCombine] Complete (%0.2fs)" % (time.time() - startTime))

def collect_from_tags(client):
    # store all original tags into integrated database
    db_recommend = client["movieRecommend"]
    db_integration = client["integration"]

    count = 0
    progressInterval = 50        # How often should we print a progress report to the console?
    progressTotal = 1128         # Approximate number of total lines in the file.

    print("[keywordsCombine] Starting collection of tags...")
    startTime = time.time()

    cursor = db_recommend["tag"].find({})
    for cur_tag in cursor:
        count += 1
        if count % progressInterval == 0:
            print("[keywordsCombine] %4d tags processed so far. (%d%%) (%0.2fs)" % (count, int(count * 100 / progressTotal), time.time() - startTime))

        cur_content = cur_tag["content"]
        movies_list = []
        scores_list = []
        if "relevant_movie" not in cur_tag:
            continue
        for relevance_pair in cur_tag["relevant_movie"]:
            attrs = relevance_pair.split(",")
            mid = int(attrs[0])
            score = float(attrs[1])
            # get the full imdb title
            relevant_movie = db_recommend["movie"].find_one({"mid": mid})
            # some mids might not exist in movieLens database
            if relevant_movie is None:
                continue
            # skip the movies with none-movie type or doesn't have full imdb title
            if "title_full" not in relevant_movie or relevant_movie["type"] != "movie":
                continue
            title = relevant_movie["title_full"]
            movies_list.append(title)
            scores_list.append(score)

        db_integration["tags"].update_one({"tag": cur_content}, {"$set": {
            "movies": movies_list,
            "scores": scores_list
            }}, True)

    print("[keywordsCombine] Complete (%0.2fs)" % (time.time() - startTime))

def combine(client):
    # combine the info from keywords and tags
    db_integration = client["integration"]

    count = 0
    progressInterval = 20      # How often should we print a progress report to the console?
    progressTotal = 360        # Approximate number of total lines in the file.

    print("[keywordsCombine] Starting combination...")
    startTime = time.time()

    tags_dict = {}
    # store all tag-movies pair in memory
    cursor = db_integration["tags"].find({})
    for cur_tag in cursor:
        cur_tag["set"] = set(cur_tag["movies"])
        tags_dict[cur_tag["tag"]] = cur_tag

    # now match and append new movies
    cursor = db_integration["keywords"].find({})
    for cur_tag in cursor:
        count += 1
        if count % progressInterval == 0:
            print("[keywordsCombine] %3d tags processed so far. (%d%%) (%0.2fs)" % (count, int(count * 100 / progressTotal), time.time() - startTime))

        if cur_tag["keyword"] not in tags_dict.keys():
            continue
        cur_dict = tags_dict[cur_tag["keyword"]]
        cur_movies_list = cur_dict["movies"]
        cur_scores_list = cur_dict["scores"]
        cur_movies_set = cur_dict["set"]

        for movie in cur_tag["relevant_movie"]:
            if movie not in cur_movies_set:
                cur_movies_set.add(movie)
                cur_movies_list.append(movie)
                cur_scores_list.append(0.7)

    for key in tags_dict.keys():
        cur_dict = tags_dict[key]
        db_integration["integrated_tag"].update_one({"tag": key}, {"$set": {
            "movies": cur_dict["movies"],
            "scores": cur_dict["scores"],
            "popularity": len(cur_dict["movies"])
            }}, True)

    print("[keywordsCombine] Complete (%0.2fs)" % (time.time() - startTime))

def fix_popularity(client):
    # store all original popularities into integrated database
    db_recommend = client["movieRecommend"]
    db_integration = client["integration"]

    count = 0
    progressInterval = 50        # How often should we print a progress report to the console?
    progressTotal = 1128         # Approximate number of total lines in the file.

    print("[keywordsCombine] Starting collection of popularities...")
    startTime = time.time()

    cursor = db_recommend["tag"].find({})
    for cur_tag in cursor:
        count += 1
        if count % progressInterval == 0:
            print("[keywordsCombine] %3d tags processed so far. (%d%%) (%0.2fs)" % (count, int(count * 100 / progressTotal), time.time() - startTime))

        cur_content = cur_tag["content"]
        db_integration["integrated_tag"].update_one({"tag": cur_content}, {"$set": {
            "popularity": cur_tag["popular"]
            }}, True)

    print("[keywordsCombine] Complete (%0.2fs)" % (time.time() - startTime))

# this functions batch and store all people names into database
# mainly for spedding up the loading phase in Recommender
def store_people_name_only(client):
    print("[keywordsCombine] Starting collection of all names...")
    startTime = time.time()

    db_integration = client["integration"]
    cursor = db_integration["peoples"].find({})
    all_names = []
    count = 0
    for cur_people in cursor:
        count += 1
        all_names.append(cur_people["people"])
        if count % 100000 == 0:
            db_integration["peoples_name_only"].insert({"names": all_names})
            all_names = []

    if count % 100000 > 0:
        db_integration["peoples_name_only"].insert({"names": all_names})

    print("[keywordsCombine] Complete (%0.2fs)" % (time.time() - startTime))

def count_movies_with_tags(client):
    db_integration = client["integration"]
    all_movies = set()
    cursor = db_integration["integrated_tag"].find({})
    for cur_tag in cursor:
        # print(cur_tag["tag"])
        if "movies" not in cur_tag:
            continue
        for movie in cur_tag["movies"]:
            all_movies.add(movie)

    print("[keywordsCombine] Totle tagged movie: " + str(len(all_movies)))

def main():
    mongo = Mongo()

    db_imdb = mongo.client["imdb"]
    db_imdb["movies"].create_index([("keywords", pymongo.ASCENDING)])
    print("[keywordsCombine] Created index for keywords in movies")

    collect_from_keywords(mongo.client) # 15 seconds

    collect_from_tags(mongo.client) # 5 minutes

    combine(mongo.client) # 8 seconds
    db_integration = mongo.client["integration"]
    db_integration["integrated_tag"].create_index([("tag", pymongo.ASCENDING)])
    print("[keywordsCombine] Created index for tag in integrated_tag")

    fix_popularity(mongo.client) # 3 seconds

    imdbPeopleIndex.build(mongo) # 3 minutes

    store_people_name_only(mongo.client) # 36 seconds

    count_movies_with_tags(mongo.client)

if __name__ == "__main__":
    main()