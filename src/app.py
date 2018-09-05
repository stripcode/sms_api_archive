import re
import asyncio
from aiohttp import web
import motor.motor_asyncio
import config
from time import time
from bson.objectid import ObjectId
from logger import logger
from tasks import sendSmsTask
from json import JSONEncoder
from datetime import datetime


cellphonePattern = re.compile("^79|89[0-9]{9}$")


class bb(JSONEncoder):
  def default(self, o):
    if isinstance(o, ObjectId):
      return str(o)
    return JSONEncoder.default(self, o)

dumps = bb().encode



# страница с описанием сервиса
async def defaultPage(request):
  readme = """
    Формат принимаего сотового телефона ^79|89[0-9]{9}$
    Длина сообщения не больше 480 символов
    http://sms.api.example.ru/sendsms?key=<key>&cellphone=<cellphone>&message=<message>
    Пример
    http://sms.api.example.ru/sendsms?key=c3499c2729730a7f807efb8676a92dcb6f8a3f8f&cellphone=79222944742&message=Привет
    http://sms.api.example.ru/sendsms?key=c3499c2729730a7f807efb8676a92dcb6f8a3f8f&cellphone=89222944742&message=Привет
    Ключ выдается отдельно.

    Возвращает хеш(уникальный id сообщения) и код 200 если смс принята, иначе 400, 401 или 5хх коды.
    Получить информации о сообщении можно так
    http://sms.api.example.ru/api/<key>/sms/<id>
    Пример
    http://sms.api.example.ru/api/c3499c2729730a7f807efb8676a92dcb6f8a3f8f/sms/58e4fc8e51356a2b1ace27a2
  """
  return web.Response(text = readme)



# сохраняет смс в базе для последующей отправки
async def sendSmsPage(request):
  cellphone = request.query.get("cellphone", None)
  message = request.query.get("message", None)
  key = request.query.get("key", None)
  logger.info("Запрос на отправку смс key = {0}, cellphone = {1}, message = {2}".format(key, cellphone, message))

  if key not in config.KEYS:
    logger.error("Нет ключа key = {0}, cellphone = {1}, message = {2}".format(key, cellphone, message))
    return web.Response(status = 401, text = "Ключ не разрешен")

  if not cellphonePattern.match(cellphone):
    logger.error("Телефон не подходит под формат key = {0}, cellphone = {1}, message = {2}".format(key, cellphone, message))
    return web.Response(status = 400, text = "Телефон не подходит под формат ^79|89[0-9]{9}$")
  if len(message) > 480:
    logger.error("Телефон не подходит под формат key = {0}, cellphone = {1}, message = {2}".format(key, cellphone, message))
    return web.Response(status = 400, text = "Длина сообщения больше 480 символов")

  msg = {
    "key": key,
    "cellphone": cellphone[-10:],
    "message": message,
    "receiveTime": time()
  }
  await request.db.sms.insert(msg)
  logger.info("Смс успешно сохранена key = {0}, cellphone = {1}, message = {2}, id = {3}".format(key, cellphone, message, msg["_id"]))
  return web.Response(text = str(msg["_id"]))



# возвращает информацию об смс
async def getSmsPage(request):
  id = request.match_info.get('id', None)
  key = request.match_info.get('key', None)
  msg = await request.db.sms.find_one({"_id": ObjectId(id), "key": key}, {"_id": 0})
  return web.json_response(msg)



# возвращает за временной промежуток
async def getSmssPage(request):
  beginDay = request.query.get('beginDay', None)
  endDay = request.query.get('endDay', None)
  messages = []
  begin = datetime.strptime(beginDay + " 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp()
  end = datetime.strptime(endDay + " 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp()
  filter = {
    "receiveTime": {
      "$gte": begin,
      "$lte": end
    }
  }
  async for msg in request.db.sms.find(filter):
    messages.append(msg)
  return web.json_response(messages, dumps = dumps)



# показывает количество неотправленных смс
async def countPage(request):
  count = await request.db.sms.find({"sendTime": {"$exists": False}}, {"_id": 0}).count()
  return web.Response(text = str(count))



async def db_handler(app, handler):
  async def middleware(request):
    request.db = app.db
    response = await handler(request)
    return response
  return middleware



app = web.Application(middlewares = [db_handler], loop = asyncio.get_event_loop())
app.client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_DSN)
app.db = app.client.sms
app.router.add_get("/", defaultPage)
app.router.add_get("/count", countPage)
app.router.add_get("/sendsms", sendSmsPage)
app.router.add_get("/api/{key}/sms/{id}", getSmsPage)
app.router.add_get("/api/{key}/sms/", getSmssPage)

app.loop.create_task(sendSmsTask(app))

if __name__ == "__main__":
  web.run_app(app, port = config.PORT)