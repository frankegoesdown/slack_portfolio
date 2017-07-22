import os
import sys
import threading
import time
import traceback

import requests
from slackclient import SlackClient

import capital
import config
import my_log
import price
import sender_file
import url_board
import select_for_portfolio
import finder
import updater
import finam.finam as finam

LOG = my_log.get_logger("main")

# starterbot's ID as an environment variable
READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose
BOT_ID = os.environ.get("BOT_ID")
TOKEN = os.environ.get('SLACK_BOT_TOKEN')
if TOKEN is None:
    TOKEN = sys.argv[1]
if BOT_ID is None:
    BOT_ID = sys.argv[2]

# constants
AT_BOT = "<@" + str(BOT_ID) + ">"

# instantiate Slack & Twilio clients
slack_client = SlackClient(TOKEN)


def handle_command(command, channel):
    global READ_WEBSOCKET_DELAY
    message = config.WELCOME
    words = str(command).split(' ')
    if words.__len__() < 1:
        response(channel, message)
        return
    first_command = words[0]
    list_extracted_files = list()
    try:
        if first_command in config.CMD_HELP:
            response(channel, config.RSP_HELP)

        if first_command in config.CMD_PRICE:
            response(channel, config.RSP_WAIT)
            message = price.price(words)
            response(channel, message)
        if first_command in config.CMD_PRICE_P:
            response(channel, config.RSP_WAIT)
            message = price.price_p(words)
            response(channel, message)

        if first_command in config.CMD_CAPITAL:
            response(channel, config.RSP_WAIT)
            message = capital.capital(words)
            response(channel, message)
        if first_command in config.CMD_CAPITAL_P:
            response(channel, config.RSP_WAIT)
            message = capital.capital_p(words)
            response(channel, message)

        if first_command in config.CMD_MOEX:
            response(channel, config.RSP_WAIT)
            response(channel, url_board.get_url(words))
        if first_command in config.CMD_MOEX_P:
            response(channel, config.RSP_WAIT)
            response(channel, url_board.get_url_p(words))

        if first_command in config.CMD_UPDATE:
            response(channel, config.RSP_WAIT)
            updater.update(words)
            response(channel, config.RSP_UPDATE_STOCK)

        if first_command in config.CMD_FILES:
            message, list_extracted_files = sender_file.send_file(words)
            response(channel, message)
            for filename in list_extracted_files:
                post_file(channel, filename)

        if first_command in config.CMD_SELECT_FOR_PORTFOLIO:
            message = select_for_portfolio.select(words)
            response(channel, message)
        if first_command in config.CMD_SELECT_FOR_PORTFOLIO_P:
            message = select_for_portfolio.select_p(words)
            response(channel, message)

        if first_command in config.CMD_GET_LIST_SELECTED:
            message = select_for_portfolio.get_list_selected()
            response(channel, message)

        if first_command in config.CMD_FIND:
            message = finder.find(words)
            response(channel, message)
        if first_command in config.CMD_FINAM_CODE:
            message = finam.loader(words)
            response(channel, message)

    except Exception:
        reset_delay()
        LOG.error(config.RSP_ERROR + " %s" % words)
        traceback.print_exc(file=sys.stdout)
        response(channel, config.RSP_ERROR)
        for file in list_extracted_files:
            threading.Thread(os.remove(file)).start()


def response(to_channel, message):
    shor_delay()
    slack_client.api_call("chat.postMessage", channel=to_channel,
                          text=message, as_user=True)


def post_file(channels, filename):
    f = {'file': (filename, open(filename, 'rb'), 'application/octet-stream', {'Expires': '0'})}
    requests.post(url='https://slack.com/api/files.upload',
                  data={'token': TOKEN, 'channels': channels, 'media': f},
                  headers={'Accept': 'application/json'}, files=f)
    LOG.info("Send file %s to channel: %s" % (filename, channels))
    rm = threading.Thread(os.remove(filename))
    rm.start()
    reset_delay()


def parse_slack_output(slack_rtm_output):
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel']
    return None, None


def parse_slack_wait(msg):
    output_list = msg
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'user' in output and BOT_ID in output['user']:
                if 'text' in output and config.RSP_WAIT in output['text']:
                    reset_delay()
                    slack_client.api_call(
                        method="chat.delete",
                        channel=output['channel'],
                        ts=output['ts'])


def welcome(msg):
    output_list = msg
    if output_list and len(output_list) > 0:
        for output in output_list:
            if 'text' in output and AT_BOT == output['text']:
                response(output['channel'], config.WELCOME)


def reset_delay():
    global READ_WEBSOCKET_DELAY
    READ_WEBSOCKET_DELAY = 1


def shor_delay():
    global READ_WEBSOCKET_DELAY
    READ_WEBSOCKET_DELAY = 0.1


def listen():
    try:
        LOG.info("StarterBot connected and running!")
        while True:
            msg = slack_client.rtm_read()
            # print(msg)
            parse_slack_wait(msg)
            welcome(msg)
            command, channel = parse_slack_output(msg)
            if command and channel:
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    except Exception:
        slack_client.rtm_connect()
        traceback.print_exc(file=sys.stdout)
        listen()

if __name__ == "__main__":

    if slack_client.rtm_connect():
        listen()
    else:
        LOG.error("Connection failed. Invalid Slack token or bot ID?")
