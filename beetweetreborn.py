import tweepy
import configparser
import re
import pickle
import logging
import sys

config = configparser.RawConfigParser()
config.read('settings.cfg')

TWEET_LEN = 140

logging.basicConfig(filename='beetweet.log', format='%(asctime)s %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())


class Beetweet:	

	def __init__(self):
		#define some useful variables
		self.consumer_key = config.get('Auth','CONSUMER_KEY')
		self.consumer_secret = config.get('Auth','CONSUMER_SECRET')
		self.access_token = config.get('Auth','ACCESS_TOKEN_KEY')
		self.access_token_secret = config.get('Auth','ACCESS_TOKEN_SECRET')
		self.username = config.get('Info', 'USERNAME')
		self.bot_name = config.get('Info', 'BOT_NAME')
		self.user_id = int(config.get('Info', 'USER_ID'))
		self.catchphrase = config.get('Info', 'CATCHPHRASE')
		#access the twitter API, get everything set up.

		auth = tweepy.OAuthHandler(self.consumer_key, self.consumer_secret)
		auth.set_access_token(self.access_token, self.access_token_secret)
		self.api = tweepy.API(auth)

		self.previous_tweets = pickle.load(open('prevtweet.pkl', 'rb'))
		self.request_list = []

		#When started, the bot will check the mentions. If there are any, it will then check if any are a valid request
		#Valid requests get the text copied and retweeted once everything has finished.
		self.get_requests()
		for i in self.request_list:
			self.verify_request(i)
			self.tweet(i)

		pickle.dump(self.previous_tweets, open('prevtweet.pkl', 'wb'))


	class TweetRequest:
		def __init__(self, req_user, req_ID, tweet_id):
			self.req_user = req_user
			self.req_ID = req_ID
			self.tweet_id = tweet_id
			self.status = ""
			self.valid = True


	def get_requests(self):
		reg = re.compile(r"^https?:\/\/twitter\.com\/(?:#!\/)?(" + self.username + "|" + str(self.user_id) + r")\/status\/(\d+)$", re.IGNORECASE) 
		#this should only get valid tweet links
		try:
			mentions = self.api.mentions_timeline(include_entities = True, since_id = self.previous_tweets['since_id'])
		except tweepy.error.TweepError as e:
			logging.error("Couldn't get mentions.")
			logging.error(e)
			return
		if len(mentions) > 0:
			self.previous_tweets['since_id'] = mentions[0].id
			mentions.reverse() #Twitter gives you mentions in chronological order, with newest first
			#This would be confusing if multiple tweets in a row were scheduled, so flip the ordering.
			for tweet in mentions:
				for url in tweet.entities['urls']:
					expanded = url['expanded_url']
					if reg.match(expanded):
						user = tweet.user.screen_name
						if user == self.bot_name: #nothing good can come from this, so disregard
							continue
						req_id = tweet.id
						tweet_id = int(re.search("(\d+)$",expanded).group(0))
						self.request_list.append(self.TweetRequest(user, req_id, tweet_id))
					else:
						continue		
			
	def verify_request(self, tweetreq): #make sure this is a valid tweet. If not, resend an appropriate error message.
	#3 cases that I can see: 1) copy of previous tweet. While you can copy tweets, there is a short cooldown on them.
	#Would rather just reuse old one
		if tweetreq.tweet_id in self.previous_tweets:
			tweetreq.status = ("I've already tweeted that! It can be found here: "
			"twitter.com/{0}/status/{1}.".format(self.bot_name, str(self.previous_tweets[tweetreq.tweet_id])))
			tweetreq.valid = False
			return
		try:
			tweet = self.api.get_status(tweetreq.tweet_id)
		except tweepy.error.TweepError as e:
	#2) Tweet doesn't exist. Easy enough
			tweetreq.status = "That tweet probably doesn't exist."
			tweetreq.valid = False
			return
		else:
	#3) Not the user's tweet. Bot should only copy one user.
			if not((tweet.user.screen_name == self.username) and (tweet.user.id == self.user_id)):
				tweetreq.status = "That tweet doesn't appear to be mine."
				tweetreq.valid = False
				return
			else:
				tweetreq.status = self.get_text(tweet)
				return

	def get_text(self, tweet):
		return (tweet.text) 
		#need to make solution for image tweets
		#unfortunately, there isn't a clean way to do this. Twitter's API doesn't let you "reuse" pictures
		#so the only other way I see is to download them off of twitter and reupload. JPEGs, so bad compression.
	
	def tweet(self, tweetreq):
		if tweetreq.valid == False:
			#because the invalid tweets would follow a different structure, I decided to split them off here.
			#Allows for the tweet to be a reply to the invalid request, too.
			text = "@" + tweetreq.req_user + " " + tweetreq.status
			if (len(text) + len(self.catchphrase) + 1 < TWEET_LEN):
				text += " " + self.catchphrase
			print(text)
			try:
				self.api.update_status(status = text, in_reply_to_status_id = tweetreq.req_ID)
			except tweepy.error.TweepError as e:
				logging.error("Error updating invalid tweet")
				logging.error(e)
			return
		else:
			#otherwise, tweet it and add it to the list
			print(tweetreq.status)
			try:
				success = self.api.update_status(status = tweetreq.status)
				self.previous_tweets[tweetreq.tweet_id] = success.id
			except tweepy.error.TweepError as e:
				logging.error("Error updating valid tweet")
				logging.error(e)
			return

Beetweets = Beetweet()
