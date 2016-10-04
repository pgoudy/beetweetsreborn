import tweepy
import configparser
import re
import pickle
import logging
import sys
import datetime
import urllib
import os

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
			self.images = []
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
				user = tweet.user.screen_name
				req_id = tweet.id
				if user == self.bot_name: #nothing good can come from this, so disregard
					continue

				if ("!status" in tweet.text.lower()): #someone is requesting a status check!
					self.request_list.append(self.TweetRequest(user, req_id, 0))
					continue #give a value of 0, will catch later.

				for url in tweet.entities['urls']:
					expanded = url['expanded_url']
					if reg.match(expanded):
						tweet_id = int(re.search("(\d+)$",expanded).group(0))
						self.request_list.append(self.TweetRequest(user, req_id, tweet_id))
					else:
						continue		
			
	def verify_request(self, tweetreq): #make sure this is a valid tweet. If not, resend an appropriate error message.
	#3 cases that I can see: 
	#0) Special status redirect
		if tweetreq.tweet_id == 0:
			tweetreq.status = datetime.datetime.now().strftime("Hello! It's currently %H:%M on %a, %B %d.")
			tweetreq.valid = False
			return
	#1) copy of previous tweet. While you can copy tweets, there is a short cooldown on them.
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
				self.get_content(tweetreq, tweet)
				return

	def get_content(self, tweetreq, tweet): #given a link to a tweet object
		text = tweet.text
		index = 0
		fileno = 0
		if hasattr(tweet, 'extended_entities'): #could probably be one line lmao
			if (len(tweet.extended_entities['media']) > 0):
				for i in tweet.extended_entities['media']:
					index = (i['indices'][0])
					fileno = fileno+1
					tweetreq.images.append(urllib.request.urlretrieve(i['media_url'],str(fileno)+".jpg")[0])
				text = text[:index] #should stay the same
		tweetreq.status =(text)
		

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
			print(tweetreq.status)
			if(len(tweetreq.images)>0):
				try:
					media_ids = [self.api.media_upload(i).media_id_string for i in tweetreq.images]
					print(media_ids)
					success = self.api.update_status(status = tweetreq.status, media_ids = media_ids)
					self.previous_tweets[tweetreq.tweet_id] = success.id
				except tweepy.error.TweepError as e:
					logging.error("Error updating valid media tweet")
					logging.error(e)
				finally:
					for i in tweetreq.images:
						print (i)
						os.remove(i)
				return
			else:
				try:
					success = self.api.update_status(status = tweetreq.status)
					self.previous_tweets[tweetreq.tweet_id] = success.id
				except tweepy.error.TweepError as e:
					logging.error("Error updating valid tweet")
					logging.error(e)
				return

Beetweets = Beetweet()
