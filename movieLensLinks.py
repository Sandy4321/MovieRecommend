import pymongo
import time

# Parsing of MovieLens links.csv file.
# db name: movieLens
# collection name: movie
# Adds fields to collection:
#       -movie id           (mid)
#       -imdb id            (imdbid)

def parse(mongo):
    progressInterval = 10000  # How often should we print a progress report to the console?
    progressTotal = 34209     # Approximate number of total lines in the file.
    bulkSize = 5000           # How many documents should we store in memory before inserting them into the database in bulk?
    # List of documents that will be given to the database to be inserted to the collection in bulk.
    bulkPayload = pymongo.bulk.BulkOperationBuilder(mongo.db["movie"], ordered = False)
    count = 0
    skipCount = 0

    print("[movieLensRatings] Starting Parse of links.csv")
    startTime = time.time()

    # open the ratings.csv and gather user's ratings into a list
    inCSV = open("movielensdata/links.csv", "r")
    # the first line is for attributes
    attrLine = inCSV.readline()

    # save all data in dict
    # output the data into MongoDB
    while 1:
        line = inCSV.readline()
        if not line:
            break

        count += 1
        if count % progressInterval == 0:
            print("[movieLensRatings] " + str(count) + " lines processed so far. (" + str(int(count * 100 / progressTotal)) + "%%) (%0.2fs)" % (time.time() - startTime))

        curAttrs = line.split(",")
        curDict = {} # {uid : ***, imdbid: ***}
        curDict["uid"] = int(curAttrs[0])
        curDict["imdbid"] = int(curAttrs[1])
        bulkPayload.insert(curDict)
        if count % bulkSize == 0:
            try:
                bulkPayload.execute()
            except pymongo.errors.OperationFailure as e:
                skipCount += len(e.details["writeErrors"])
            bulkPayload = pymongo.bulk.BulkOperationBuilder(mongo.db["user_rate"], ordered = False)
    try:
        bulkPayload.execute()
    except pymongo.errors.OperationFailure as e:
        skipCount += len(e.details["writeErrors"])


    print("[movieLensRatings] Parse Complete (%0.2fs)" % (time.time() - startTime))
    print("[movieLensRatings] Found " + str(count) + " movies.")
    print("[movieLensRatings] Skipped " + str(skipCount) + " insertions.")
