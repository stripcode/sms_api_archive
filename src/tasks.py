import config
import re
import csv
from aiohttp import ClientSession
import async_timeout
import asyncio
from logger import logger
from time import time
from urllib.parse import urlencode

codes = {}
timeout = 3

regionPattern = re.compile(".*Сверд.*")
megafonPattern = re.compile(".*Мега.*")
motivPattern = re.compile(".*ЕКАТЕРИНБУРГ-2000.*")


def prepare_parts(cellphone):
  return cellphone[-10:3], cellphone[-7:]

def getOperator(cellphone):
  prefix, number = prepare_parts(cellphone)
  prefix = int(prefix)
  number = int(number)
  target = "beeline"
  if prefix in codes:
    for diap in codes[prefix]:
      begin, end, operator = diap
      if number >= begin and number <= end:
        target = operator
  return target



def loadDiap(row, operator):
  prefix = int(row[0].strip())
  begin = int(row[1].strip())
  end = int(row[2].strip())
  if prefix not in codes:
    codes[prefix] = []
  codes[prefix].append((begin, end, operator))
  logger.info("Загружен диапазон {0} prefix = {1}, begin = {2}, end = {3}".format(operator, prefix, begin, end))



# отправка через мегафон
async def sendMegafon(cellphone, message):
  logger.info("Попытка отослать смс через мегафон cellphone = {0}, message = {1}".format(cellphone, message))
  params = {
    "username": "crm",
    "password": "crm",
    "to": "7" + cellphone,
    "text": message.encode("utf-16-be"),
    "coding": 2
  }
  # сделано так не спроста
  # прямым путем не принимает байты в сообщении
  params = urlencode(params)
  async with ClientSession() as session:
    with async_timeout.timeout(timeout, loop = session.loop):
      # http интерфейс kannel мегафон
      async with session.get("http://10.0.3.13:13005/cgi-bin/sendsms", params = params) as resp:
        text = await resp.text()
        print(text)



# отправка через мотив
async def sendMotiv(cellphone, message):
  logger.info("Попытка отослать смс через мотив cellphone = {0}, message = {1}".format(cellphone, message))
  params = {
    "username": "crm",
    "password": "crm",
    "to": "7" + cellphone,
    "text": message.encode("utf-16-be"),
    "coding": 2
  }
  # сделано так не спроста
  # прямым путем не принимает байты в сообщении
  params = urlencode(params)
  async with ClientSession() as session:
    with async_timeout.timeout(timeout, loop = session.loop):
      # http интерфейс kannel мотив
      async with session.get("http://10.0.3.18:13005/cgi-bin/sendsms", params = params) as resp:
        text = await resp.text()
        print(text)



# Отправка через билайн
async def sendBeeline(cellphone, message):
  logger.info("Попытка отослать смс через билайн cellphone = {0}, message = {1}".format(cellphone, message))
  data = {
    'user': "example",
    'pass': 'example',
    'sender': 'example',
    'action': 'post_sms',
    'target': "7" + cellphone,
    'message': message
  }
  async with ClientSession() as session:
    with async_timeout.timeout(timeout, loop=session.loop):
      async with session.post("https://beeline.amega-inform.ru/sendsms/", data = data) as resp:
        text = await resp.text()
        print(text)



# периодическая задача по отправке смс
# если телефон мегафон или мотив то отсылает через мегафон
# иначе отсылает через билайн
async def sendSmsTask(app):
  try:
    collection = app.db.sms
    async for m in collection.find({"sendTime": {"$exists": False}}).limit(5):
      operator = getOperator(m["cellphone"])
      if operator == "megafon":
        await sendMegafon(m["cellphone"], m["message"])
      elif operator == "motiv":
        await sendMotiv(m["cellphone"], m["message"])
      else:
        await sendBeeline(m["cellphone"], m["message"])
      upd = {
        "$set":{
          "operator": operator,
          "sendTime": time()
        }
      }
      await collection.update_one({"_id": m["_id"]}, upd)
  except Exception as e:
    logger.error(e)
  finally:
    await asyncio.sleep(0.5)
    app.loop.create_task(sendSmsTask(app))



logger.info("Загрузка файла с диапазонами {0}".format(config.CODE_FILE))
with open(config.CODE_FILE, encoding = "cp1251") as csvfile:
  spamreader = csv.reader(csvfile, delimiter=';')
  for row in spamreader:
    if len(row) != 6:
      raise RuntimeError("Не смог распарсить файл диапазонов {0}".format(config.CODE_FILE))
    companyName = row[4].strip()
    regionName = row[5].strip()
    if regionPattern.match(regionName) and megafonPattern.match(companyName):
      loadDiap(row, "megafon")
    elif regionPattern.match(regionName) and motivPattern.match(companyName):
      loadDiap(row, "motiv")
  logger.info("Файл с диапазонами {0} успешно загружен".format(config.CODE_FILE))
