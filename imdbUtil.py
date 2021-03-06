from datetime import date
import re

#Cases:
#	Single year (2003)
#	Range (2003-2010) -> return earliest year in range
#	Unknown (non-numerical value) -> In IMDB, "????" is used to mean "currently airing/no release date announced yet"... return current year
def parseYear(year):
	if "-" in year:
		return year[:year.index("-")]
	try:
		int(year)
		return year
	except ValueError:
		return date.today().year

#IMDB Title Format:
#	TITLE (YEAR) {EPISODE}
#	If episode included, then it is a TV show, not a movie.
def isEpisode(title):
	if "{" in title:
		return True
	return False

#Strips TV episode from IMDB title
def stripEpisode(title):
	return re.sub(r"\s{.*}", "", title)

#Formats IMDB title as it should appear in the database
def formatTitle(title):
	removeDesc = title
	if "  (" in removeDesc:
		removeDesc = title[:title.index("  (")]
	if "  [" in removeDesc:
		removeDesc = removeDesc[:removeDesc.index("  [")]
	if "  <" in removeDesc:
		removeDesc = removeDesc[:removeDesc.index("  <")]
	return removeDesc.replace('"', '').encode('ascii', 'ignore').decode('ascii').strip()

#Strips all information from the IMDB title except for the title itself (year, episode, etc)
def simpleTitle(title):
	titlef = formatTitle(title)
	if "(" in titlef:
		return titlef[:titlef.index('(')-1]
	else:
		return titlef

#Reformat names from "Last, First" to "First Last", and etc.
def formatName(name):
	trimmedName = name
	if "(" in name:
		trimmedName = name[:name.index("(")-1]
	if "," in trimmedName:
		return trimmedName[trimmedName.index(",")+2:]+" "+trimmedName[:trimmedName.index(",")]
	return formatTitle(trimmedName)