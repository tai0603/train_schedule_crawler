import os, sys
import requests
import pandas
import numpy
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime

from flask import Flask, request, abort

from linebot import (
	LineBotApi, WebhookHandler
)
from linebot.exceptions import (
	InvalidSignatureError
)
from linebot.models import *

app = Flask(__name__)

# Channel Access Token
line_bot_api = LineBotApi('')
# Channel Secret
handler = WebhookHandler('')

# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
	# get X-Line-Signature header value
	signature = request.headers['X-Line-Signature']
	# get request body as text
	body = request.get_data(as_text=True)
	app.logger.info("Request body: " + body)
	# handle webhook body
	try:
		handler.handle(body, signature)
	except InvalidSignatureError:
		abort(400)
	return 'OK'

# 處理訊息
@handler.add(MessageEvent, message = TextMessage)
def handle_message(event):
	send_text = event.message.text
	if re.match('/train', send_text):
		instr = send_text.split()
		#message = TextSendMessage(text = train_schedule(trainStation_code(instr[1]), trainStation_code(instr[2])))
		message = FlexSendMessage(
			alt_text = "🚂火車時刻表出來囉", 
			contents = train_schedule(trainStation_code(instr[1]), trainStation_code(instr[2]))
		)
		line_bot_api.reply_message(event.reply_token, message)

# 火車時刻表
def train_schedule(fromStation, toStation):
	today = datetime.today().strftime('%Y/%m/%d')
	current_time = datetime.now().strftime("%H:%M")

	headers = {
		'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36',
		'Content-Type': 'application/x-www-form-urlencoded',
		'Connection': 'close'
	}
	Form_Data = {
		'startStation': fromStation,
		'endStation': toStation,
		'transfer': 'ONE',
		'rideDate': today,
		'startOrEndTime': 'true',
		'startTime': current_time,
		'endTime': '23:59',
		'trainTypeList': 'ALL',
		'query': '查詢'
	}
	url = 'https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytime'

	response = requests.post(url, params = Form_Data, headers = headers)
	
	soap = BeautifulSoup(response.text, 'html.parser')

	schedule = ''
	text_count = 0

	flex =  {
			  "type": "carousel",
			  "contents": 
			  [
				{
				  "type": "bubble",
				  "header": {
					"type": "box",
					"layout": "vertical",
					"contents": 
					[
					  {
						"type": "box",
						"layout": "vertical",
						"contents": 
						[
						  {
							"type": "text",
							"text": "FROM",
							"size": "sm",
							"color": "#ffffff66"
						  },
						  {
							"type": "text",
							"text": fromStation.strip('-0123456789'),
							"flex": 4,
							"size": "xl",
							"color": "#ffffff",
							"weight": "bold"
						  }
						]
					  },
					  {
						"type": "box",
						"layout": "vertical",
						"contents": 
						[
						  {
							"type": "text",
							"text": "TO",
							"size": "sm",
							"color": "#ffffff66"
						  },
						  {
							"type": "text",
							"text": toStation.strip('-0123456789'),
							"flex": 4,
							"size": "xl",
							"color": "#ffffff",
							"weight": "bold"
						  }
						]
					  }
					],
					"spacing": "md",
					"height": "154px",
					"backgroundColor": "#0367D3"
				  },
				  "body": 
				  {
					"type": "box",
					"layout": "vertical",
					"contents": 
					[
					  {
						"type": "text",
						"text": today,
						"align": "start"
					  },
					  {
						"type": "separator"
					  }
					]
				  }
				}
			  ]
			}

	#error
	errorDiv = soap.select('#errorDiv[style != "display: none"]')
	if errorDiv != []:
		error_alert = errorDiv[0].select('.icon-fa.mag-error')
		for e in error_alert:
			schedule += '❌' + e.text.strip() + '\n'
		schedule = schedule.strip()

		flex['contents'][0]['body']['contents'].append({
															"type": "box",
															"layout": "vertical",
															"contents": 
															[
															  {
																"type": "text",
																"text": schedule,
																"size": "lg",
																"align": "start",
																"wrap": True
															   }
															 ]
														   })
	else:
		#查無資料
		no_data = soap.select('.alert.alert-warning')

		if no_data == []:
			Time_table = pandas.read_html(response.text)

			i = 0
			for train in Time_table:
				if i > 0:
					time = numpy.array(train)

					# 車種, 出發時間, 抵達時間[0, 1, 3]
					time[0, 1] = time[0, 1].split(' ')
					time[0, 3] = time[0, 3].split(' ')

					#計算是否超過2500字
					text_count += len(time[0, 0]) + len(time[0, 1][0]) + len(time[0, 3][0])
					if text_count > 2500:
						flex['contents'][0]['body']['contents'].pop()
						break

					flex['contents'][0]['body']['contents'].append({
																	 "type": "box",
																	 "layout": "horizontal",
																	 "spacing": "sm",
																	 "contents": [
																	   {
																		 "type": "box",
																		 "layout": "vertical",
																		 "flex": 5,
																		 "contents": [
																		   {
																			 "type": "text",
																			 "size": "lg",
																			 "text": time[0, 0],
																			 "align": "start",
																			 "wrap": True
																		   },
																		   {
																			 "type": "box",
																			 "layout": "baseline",
																			 "spacing": "sm",
																			 "contents": [
																			   {
																				 "type": "text",
																				 "text": time[0, 1][0],
																				 "flex": 3,
																				 "align": "start"
																			   },
																			   {
																				 "type": "text",
																				 "text": time[0, 3][0],
																				 "flex": 1,
																				 "align": "center"
																			   }
																			 ]
																		   }
																		 ]
																	   }
																	 ]
																   })
					if i != len(Time_table) - 1:
						flex['contents'][0]['body']['contents'].append({
																		 "type": "separator"
																	   })
				i = i + 1
		else:
			schedule = '⚠️' + no_data[0].text.strip()

			flex['contents'][0]['body']['contents'].append({
															"type": "box",
															"layout": "vertical",
															"contents": 
															[
															  {
																"type": "text",
																"text": schedule,
																"size": "lg",
																"align": "start",
																"wrap": True
															   }
															 ]
														   })

	return flex

# 火車站代碼
def trainStation_code(station):
	with open('Station Code.json', 'r', encoding = "utf-8") as f:
		stationDic = json.load(f)
	
	for s in stationDic:
		if station == s:
			return stationDic[s] + '-' + s
			break

# 火車時刻表flex message
#def trainSchedule_Flex(date, start, end):


if __name__ == "__main__":
	port = int(os.environ.get('PORT', 5000))
	app.run(host='0.0.0.0', port=port)