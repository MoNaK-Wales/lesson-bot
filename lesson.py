import telebot
import threading
import datetime as dt
from time import sleep
import requests
from tt import tt       #расписание звонков
from config import *    #расписание с ссылками, учителя, токен бота, список айди для упоминания, чс, айди мест тревог

bot = telebot.TeleBot(botToken)

with open("tt.py", "w") as f:
    f.write("""import datetime as dt 
tt = {
    1 : [dt.timedelta(hours= 9, minutes=40), dt.timedelta(minutes=40)],
    2 : [dt.timedelta(hours=10, minutes=25), dt.timedelta(minutes=40)],
    3 : [dt.timedelta(hours=11, minutes=15), dt.timedelta(minutes=40)],
    4 : [dt.timedelta(hours=12, minutes=00), dt.timedelta(minutes=40)],
    5 : [dt.timedelta(hours=12, minutes=50), dt.timedelta(minutes=40)],
    6 : [dt.timedelta(hours=13, minutes=35), dt.timedelta(minutes=40)],
    7 : [dt.timedelta(hours=14, minutes=20), dt.timedelta(minutes=40)],
    8 : [dt.timedelta(hours=15, minutes= 5), dt.timedelta(minutes=40)],
}""")

timeTable = tt
eightLessonWeekday = [1]                            #день, когда 8 уроков: понедельник
noLessonsText = "уроков нет"                        #что пишется, когда нет уроков
alert = False                                       #есть ли тревога
tr = threading.Thread()                             #поток для параллельной проверки тревог

@bot.message_handler(commands=["lesson"])               #основная команда
def getLesson(message):                                   
    global tr
    chat = message.chat.id

    if message.from_user.id in blackList:           #чс для плохих людей
        bot.send_message(chat, "пошёл в жопу")
        return

    zone = dt.timezone(dt.timedelta(hours=2))       #получение времени по Киеву
    time = dt.datetime.now(zone)
    weekday = time.isoweekday()

    if not tr.is_alive():                           #запуск проверки тревог, если еще не запущен
        tr = threading.Thread(target=checkAlerts, kwargs={'bot': bot, 'chat': chat}, name="checking")
        tr.start()

    if weekday in range(6):                                                             #проверка на будни
        lesson, endTime, lessonTime = getLessonNum(time)

        if lesson > 8 or (lesson > 7 and not weekday in eightLessonWeekday):            #урок не больше 7 или 8 в день с 8 уроками
            bot.send_message(chat, noLessonsText)
        elif lesson > 0:                                                                #урок
            mes = ""

            if alert: mes += "🚨Тревога!🚨"                                            #есть ли тревога
            mes += str(lesson) + ". "                                                   #номер урока
            mes += shedule[weekday][lesson] + "\n"                                      #сам урок

            startTime = dt.datetime.strptime(str(endTime - lessonTime), "%H:%M:%S")     #время урока
            endTime = dt.datetime.strptime(str(endTime), "%H:%M:%S")
            mes += f"{startTime.strftime('%H:%M')} - {endTime.strftime('%H:%M')} \n"

            mes += teachers[shedule[weekday][lesson].split(" ")[0]]                     #учитель

            bot.send_message(chat, mes)
    else:
        bot.send_message(chat, noLessonsText)

@bot.message_handler(commands=["changeTime"])           #команда для изменения расписания
def changeTime(message):                                        
    chat = message.chat.id
    messages = message.text.split("\n")[1:]

    if message.from_user.id != owner_id:
        bot.send_message(chat, "Менять время может только создатель бота")
        return
    elif len(messages) != 8:
        bot.send_message(chat, "Временных промежутков должно быть 8\nПример правильного написания:\n/changeTime\n8:00 9:00\n9:10 10:00\n..")
        return

    with open("tt.py", "r") as f:
        startLines = f.readlines()[:2]
    with open("tt.py", "w") as f:
        f.write(startLines[0])
        f.write(startLines[1])

        for i in range(8):
            end = messages[i].split(' ')[1]
            length = dt.datetime.strptime(end, "%H:%M") - dt.datetime.strptime(messages[i].split(' ')[0], "%H:%M")
            f.write(f"    {i+1} : [dt.timedelta(hours={end.split(':')[0]}, minutes={end.split(':')[1]}), dt.timedelta(minutes={length.seconds//60})],\n")

            timeTable[i+1] = [dt.timedelta(hours=int(end.split(':')[0]), minutes=int(end.split(':')[1])), dt.timedelta(minutes=length.seconds//60)]
        f.write("}")
    bot.send_message(chat, "Изменено")

def checkAlerts(bot, chat):
    global alert
    while True:
        regionInfos = []
        hangUp = 0
        for id in region_ids:
            try:
                regionInfos.append(requests.get(sirenAPI+str(id)).json()[0]['activeAlerts'])
            except Exception as e:
                print(e)
        if (len(regionInfos[0]) != 0 or len(regionInfos[1]) != 0 or len(regionInfos[2]) != 0) and not alert:
            bot.send_message(chat, "🚨Тревога🚨")
            alert = True
        if (len(regionInfos[0]) == 0 and len(regionInfos[1]) == 0 and len(regionInfos[2]) == 0) and alert:
            bot.send_message(chat, "✅Отбой")
        sleep(7)

def mentionAll(bot, chat):
    text = "Отбой тревоги"
    mes = ""
    for i in range(len(mention)):
        if i < len(text):
            mes += f"[{text[i]}](tg://user?id={mention[i]})"
        else:
            mes += f"[✅](tg://user?id={mention[i]})"
    bot.send_message(chat, mes, parse_mode="MarkdownV2")

def getLessonNum(time):
    td = dt.timedelta(hours=time.hour, minutes=time.minute)
    for les in timeTable:
        if td < timeTable[les][0] and td > timeTable[min(timeTable.keys())][0] - dt.timedelta(minutes=60):
            return les, timeTable[les][0], timeTable[les][1]
    return 9, 0, 0

def poll():
    try:
        bot.polling(none_stop=True, interval=0)
    except requests.exceptions.ReadTimeout:
        print("timeout")
        poll()
    except requests.exceptions.ProxyError:
        print("proxy")
        poll()
poll()
