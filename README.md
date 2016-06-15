# beetweetsreborn

Beetweets is a python script that copies the text of certain tweets on demand, so that they can be retweeted. Most helpful if you have a private account that would like basic retweeting functionality, but still be private.

## Setup

In order for beetweets to run properly, the following are needed:
* Tweepy
* The Access Tokens from https://apps.twitter.com - these need to be from the account that will be retweeting, not your main account
* The Username and ID for each account.

Place the relevant info in each field in the settings.cfg file. Change the catchphrase if you desire, but keep it short. It'll be appended to most error messages.

Additionally, a job scheduler like cron should be used to run the script as often as you would like. Once per minute is the rate I found worked the best, as the twitter API will only allow 15 requests of the mentions timeline every 15 minutes.

## Use

To have Beetweets copy one of your tweets, mention her in a tweet along with a link to the tweet desired to be copied. Assuming that it is one of yours, the tweet will be copied and posted on the account shortly.

If there is an error, she will reply to the mention with hopefully relevant info.
