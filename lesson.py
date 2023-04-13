import telebot
import threading
import datetime as dt
from time import sleep
import requests
from config import *    #расписания, учителя, токен бота, мой айди, список айди для упоминания, чс, айди мест тревог, апи тревог

bot = telebot.TeleBot(botToken)

eightLessonWeekday = [1]                            #день, когда 8 уроков: понедельник
noLessonsText = "уроков нет"                        #что пишется, когда нет уроков
alert = False                                       #есть ли тревога
tr = threading.Thread()                             #поток для параллельной проверки тревог

@bot.message_handler(commands=["lesson"])               #основная команда
def getLesson(message):                                   
    global tr
    chat = message.chat.id

    if chat != chatMain_id and message.from_user.id != botOwner_id:                     #чтобы ссылки не попали в плохие руки
        bot.send_message(chat, "Бота можно использовать только в школьной группе")
        return

    if message.from_user.id in blackList:           #чс для плохих людей
        bot.send_message(chat, "пошёл в жопу")
        return

    zone = dt.timezone(dt.timedelta(hours=3))       #получение времени по Киеву
    time = dt.datetime.now(zone)
    weekday = time.isoweekday()

    if not tr.is_alive():                           #запуск проверки тревог, если еще не запущен
        tr = threading.Thread(target=checkAlerts, kwargs={'bot': bot, 'chat': chat, 'zone': zone}, name="checking")
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

@bot.message_handler(commands=["changeTime"])                   #команда для изменения расписания
def changeTime(message):                                        
    chat = message.chat.id
    member = bot.get_chat_member(chat, message.from_user.id)
    timesRows = message.text.split("\n")[1:]                    #8 строк со временем начала и конца каждого урока после строки команды

    #команду может использовать только владелец бота, создатель и администратор. строк со временем должно быть 8
    if member.user.id != botOwner_id and member.status != "creator" and member.status != "administrator": 
        bot.send_message(chat, "Менять время могут только администраторы")
        return
    elif len(timesRows) != 8:                                                               
        bot.send_message(chat, "Временных промежутков должно быть 8\nПример правильного написания:\n/changeTime\n8:00 9:00\n9:10 10:00\n..")
        return

    for i in range(8):                                      #итерация по строкам со временем
       times = timesRows[i].split(' ')                                                              #отдельная строка     
       length = dt.datetime.strptime(times[1], "%H:%M") - dt.datetime.strptime(times[0], "%H:%M")   #время урока

       hoursMinutes = times[1].split(':')                                                           #отдельно время начала и конца
       timeTable[i+1] = [dt.timedelta(hours=int(hoursMinutes[0]), minutes=int(hoursMinutes[1])), dt.timedelta(minutes=length.seconds//60)]
    bot.send_message(chat, "Изменено") 



def checkAlerts(bot, chat, zone):       #проверка, есть ли хоть в одном заданном месте тревога
    global alert

    while True:                         #тревога проверяется постоянно, каждые 7 секунд
        regionInfos = []
        check = lambda x: len(x) != 0
        
        for id in region_ids:
            try:                        #получение для каждого места списка активных тревог, который пустой, если тревоги нет
                regionInfos.append(requests.get(sirenAPI+str(id)).json()[0]['activeAlerts'])
            except Exception as e:
                print(e)

        time = dt.datetime.now(zone)
        delta = dt.timedelta(hours= time.hour, minutes=time.minute)
        alert_ids = list(filter(check, regionInfos))                            #фильтрация пустых списков (мест без тревоги)
        if len(alert_ids) != 0 and not alert and delta < timeTable[8][0]:       #оповещение про тревогу до конца учебы
            bot.send_message(chat, "🚨Тревога🚨")
            alert = True
        if len(alert_ids) == 0 and alert:
            mentionAll(bot, chat)
            alert = False
        sleep(7)

def mentionAll(bot, chat):              #функция для того, чтобы отметить в тексте всех заданных участников
    text = "Отбой тревоги"
    mes = ""
    for i in range(len(mention)):
        if i < len(text):
            mes += f"[{text[i]}](tg://user?id={mention[i]})"    #в каждую букву вставляется ссылка для пинга
        else:                                                               
            mes += f"[✅](tg://user?id={mention[i]})"           #если участников больше, чем букв, остальные добавляются в смайлик
    bot.send_message(chat, mes, parse_mode="MarkdownV2")


def getLessonNum(time):                                             #функция для получения номера урока
    td = dt.timedelta(hours=time.hour, minutes=time.minute)
    for les in timeTable:
        #возвращается первый урок (+его время и длина), время конца которого будет больше, чем время сейчас (и за час до первого урока)
        if td < timeTable[les][0] and td > timeTable[min(timeTable.keys())][0] - (timeTable[1][1]+dt.timedelta(minutes=60)):
            return les, timeTable[les][0], timeTable[les][1]        #кроме урока еще возвращается время его конца и длина
    return 9, 0, 0


def poll():         #запуск бота и обработка некоторых ошибок
    try:
        bot.polling(none_stop=True, interval=0)
    except requests.exceptions.ReadTimeout:
        print("timeout")
        poll()
    except requests.exceptions.ProxyError:
        print("proxy")
        poll()
    except requests.exceptions.ConnectionError:
        print("connection")
        poll()
poll()
