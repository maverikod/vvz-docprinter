import json
import os.path

class MessagesContainer:
    def __init__(self, messages_data = None):
        self.msg = None
        if isinstance(messages_data, dict):
            self.msg = messages_data 
        elif isinstance(messages_data,(str,int)):
            if os.path.exists(messages_data) and os.path.isfile(messages_data):
                self.load_messages_from_file(messages_data)
        if not isinstance(self.msg,dict):
            self.msg = {
                "000":{
                     'en_us':"Success"
                    ,'uk_ua':"Вдало"
                    ,'ru_ru':"Удачно"
                }
                ,"001":{
                     'en_us':"File not found: {file}"
                    ,'uk_ua':"Файл не знайдено: {file}"
                    ,'ru_ru':"Файл не найден {file}"
                }
                ,"002":{
                     'en_us':"Invalid JSON format in input file: {file}"
                    ,'uk_ua':"Помилка JSON формату у файлі: {file}"
                    ,'ru_ru':"Ошибка JSON формата в файле: {file}"
                }
                ,"003":{
                     'en_us':"Invalid data format in file: {file}\n{error}"
                    ,'uk_ua':"Невірний формат даних у файлі: {file}\n{error}"
                    ,'ru_ru':"Неверный формат данных в файле: {file}\n{error}"
                }
                ,"004":{
                     'en_us':"Current user has no permission to read file: {file}"
                    ,'uk_ua':"Поточний користувач не має прав на читання файла: {file}"
                    ,'ru_ru':"Текущий пользователь не имеет прав на чтение файла: {file}"
                }
                ,"999":{
                     'en_us':"No message available in locale '{locale}' for code {code}"
                    ,'uk_ua':"В локали {locale} не найдено сообщение с кодом {code}"
                    ,'ru_ru':"У локалі {locale} не знайдено повідомлення з кодом {code}"
                }
                ,"998":{
                     'en_us':"Properties 'cmd' and 'data' must be present in the incoming data"
                    ,'uk_ua':"Властивості 'cmd' та 'data' повинні бути присутніми у вхідних даних"
                    ,'ru_ru':"Свойства 'cmd' и 'data' должны быть представлены во входных данных"
                }
                ,"997":{
                     'en_us':"Invalid JSON format in input file: {infile}"
                    ,'uk_ua':"Помилка JSON формату у вхідному файлі: {infile}"
                    ,'ru_ru':"Ошибка JSON формата во входном файле: {infile}"
                }
                ,"996":{
                     'en_us':"Module not found: {cmd}, path:{path}"
                    ,'uk_ua':"Модуль не знайдено: {cmd}, path:{path}"
                    ,'ru_ru':"Модуль не найден: {cmd}, path:{path}"
                }
                ,"995":{
                     'en_us':"Module '{cmd}' does not have 'run' method"
                    ,'uk_ua':"Модуль '{cmd}' не підтримує метод 'run'"
                    ,'ru_ru':"Модуль '{cmd}' не поддерживает метод 'run'"
                }
                ,"994":{
                     'en_us':"Error occured in plugin '{cmd}': {errstr}"
                    ,'uk_ua':"Трапилася помилка у плагіні '{cmd}'  {errstr}"
                    ,'ru_ru':"Произошла ошибка в плагине '{cmd}'  {errstr}"
                }
                ,"993":{
                     'en_us':"Error opening file for writing: {file}"
                    ,'uk_ua':"Помилка відкриття файлу на запис: {file}"
                    ,'ru_ru':"Ошибка открытия файла на запись: {file}"
                }
                ,"992":{
                     'en_us':"Argument error : {error}"
                    ,'uk_ua':"Помилка аргументу: {error}"
                    ,'ru_ru':"Ошибка аргумента: {error}"
                }
                ,"991":{
                     'en_us':"Data for plugin RAC 1C must be dictionary"
                    ,'uk_ua':"Дані для плагина RAC 1C повинні бути словником "
                    ,'ru_ru':"Данные для плагина RAC 1C должны быть словарем"
                }
                ,"990":{
                     'en_us':"Property cmd must be present in data for plugin RAC 1C"
                    ,'uk_ua':"Відсутня обов'язкова властивість cmd у даних для плагіна RAC 1C"
                    ,'ru_ru':"Обязательное свойство cmd должно быть в предствлено в данных для плагина RAC 1C"
                }
                ,"989":{
                     'en_us':"Unknown command for plugin RAC 1C '{errstr}'"
                    ,'uk_ua':"Неопізнана команда для плагіна RAC 1C '{errstr}'"
                    ,'ru_ru':"Неизвестная команда для плагина RAC 1C '{errstr}'"
                }
                ,"988":{
                     'en_us':"Arguments infile, outfile, log, data are required '{errstr}'"
                    ,'uk_ua':"Необходимые аргументы не указаны: infile, outfile, log, data '{errstr}'"
                    ,'ru_ru':"Необхiднi документи не вказано: infile, outfile, log, data  '{errstr}'"
                }
                ,"987":{
                     'en_us':"Arguments infile, outfile, log, data are required '{errstr}'"
                    ,'uk_ua':"Необходимые аргументы не указаны: infile, outfile, log, data '{errstr}'"
                    ,'ru_ru':"Необхiднi документи не вказано: infile, outfile, log, data  '{errstr}'"
                }
                ,"986":{
                     'en_us':"Template error:  '{errstr}'"
                    ,'uk_ua':"Помилка у шаблонi: '{errstr}'"
                    ,'ru_ru':"Ошибка в шаблоне:  '{errstr}'"
                }
                ,"985":{
                     'en_us':"Template not found: '{errstr}'"
                    ,'uk_ua':"Шаблон не знайдено: '{errstr}'"
                    ,'ru_ru':"Шаблон не найден: '{errstr}'"
                }
                ,"984":{
                     'en_us':"Template syntax error: '{errstr}'"
                    ,'uk_ua':"Помилка у шаблонi: '{errstr}'"
                    ,'ru_ru':"Ошибка в шаблоне  '{errstr}'"
                }
                ,"983":{
                     'en_us':"Invalid data: '{errstr}'"
                    ,'uk_ua':"Невiрний формат даних '{errstr}'"
                    ,'ru_ru':"Неверный формат Данных  '{errstr}'"
                }
                ,"982":{
                     'en_us':"Undefined key in template: '{errstr}'"
                    ,'uk_ua':"Невiдомий ключ у шаблонi: '{errstr}'"
                    ,'ru_ru':"Неизвестный ключ в шаблоне: '{errstr}'"
                }
                ,"981":{
                     'en_us':"Internal error in docxtpl:  '{errstr}'"
                    ,'uk_ua':"Внутрiшня помилка у бiблiотецi docxtpl:  '{errstr}'"
                    ,'ru_ru':"Внутренняя ошибка в библиотеке docxtpl:   '{errstr}'"
                }
                ,"980":{
                     'en_us':"Template syntax error: '{errstr}'"
                    ,'uk_ua':"Синтаксична помилка у шаблонi: '{errstr}'"
                    ,'ru_ru':"Синтаксическая ошибка в шаблоне: '{errstr}'"
                }
                ,"979":{
                     'en_us':"I/O error: '{errstr}'"
                    ,'uk_ua':"Помилка вводу/виводу: '{errstr}'"
                    ,'ru_ru':"Ошибка ввода/вывода: '{errstr}'"
                }
                ,"978":{
                     'en_us':"Bad format of input JSON object. The 'cmd' property must be present. {errstr}"
                    ,'uk_ua':"Помилковий формат вхiдного об`єкту JSON. Вiдсутня властивiсть 'cmd'. {errstr}"
                    ,'ru_ru':"Ошибочный формат входного об JSON. Отсутствует свойство 'cmd'. {errstr}"
                }
                ,"977":{
                     'en_us':"Bad format of input JSON object. The 'outfile' property must be present. {errstr}"
                    ,'uk_ua':"Помилковий формат вхiдного об`єкту JSON. Вiдсутня властивiсть 'outfile'. {errstr}"
                    ,'ru_ru':"Ошибочный формат входного об JSON. Отсутствует свойство 'outfile'. {errstr}"
                }
                ,"976":{
                     'en_us':"Bad format of input JSON object. The 'data' property must be present. {errstr}"
                    ,'uk_ua':"Помилковий формат вхiдного об`єкту JSON. Вiдсутня властивiсть 'data'. {errstr}"
                    ,'ru_ru':"Ошибочный формат входного об JSON. Отсутствует свойство 'data'. {errstr}"
                }
                ,"975":{
                     'en_us':"Arguments template and outfile are required"
                    ,'uk_ua':"Необходимые аргументы не указаны: template та outfile"
                    ,'ru_ru':"Необхiднi документи не вказано: template и outfile"
                }
                ,"974":{
                     'en_us':"Plugin returned wrong data format."
                    ,'uk_ua':"Плагiн повернув данi у помилковому форматi."
                    ,'ru_ru':"Плагин вернул данные в ошибочном формате."
                }
                ,"973":{
                     'en_us':"Arguments indir and outdir are required"
                    ,'uk_ua':"Необходимые аргументы не указаны: indir та outdir"
                    ,'ru_ru':"Необхiднi документи не вказано: indir и outdir"
                }
                ,"972":{
                     'en_us':"{outdir} is a file, but not a folder."
                    ,'uk_ua':"{outdir} є файлом. Повинен бути папкою."
                    ,'ru_ru':"{outdir} это файл, а должен быть папкой."
                }
                ,"971":{
                     'en_us':"Permission denied for write into {outdir}."
                    ,'uk_ua':"Недостатньо прав для запису у  каталог {outdir}."
                    ,'ru_ru':"Недостаточно прав для записи в каталог {outdir}."
                }
                ,"970":{
                     'en_us':"Can't create output folder {outdir}."
                    ,'uk_ua':"Не вдалося створити каталог з вихідними даними {outdir}."
                    ,'ru_ru':"Не удалось создать каталог с выходными данными {outdir}."
                }
                ,"969":{
                     'en_us':"Folder {indir} not found."
                    ,'uk_ua':"Каталог {indir} не знайдено."
                    ,'ru_ru':"Каталог {indir} не найден."
                }
            }

    def load_messages_from_file(self, file_name):
        try:
            with open(file_name, 'r') as f:
                messages_data = json.load(f)
                self.msg = messages_data
            return messages_data
        except (FileNotFoundError, PermissionError):
            print(f"Error: could not read file '{file_name}'")
            return {}

    def save_messages_to_file(self, file_name):
        try:
            with open(file_name, 'w') as f:
                json.dump(self.msg, f, indent=4)
            print(f"Messages saved to file '{file_name}'")
        except (FileNotFoundError, PermissionError):
            print(f"Error: could not write to file '{file_name}'")

    def getmsg(self, code=0, locale="en_US",data={}):
        code_str = f"{code:03}"
        if not isinstance(locale,str):
            locale_lower = "en_US"
        else:
            locale_lower = locale.lower()
        if code_str in self.msg:
            if locale_lower in self.msg[code_str]:
                _data = data if isinstance(data,dict) else {}
                try:
                    return self.msg[code_str][locale_lower].format_map(_data)
                except KeyError:
                    return self.msg[code_str][locale_lower]
            elif locale_lower in self.msg["999"]:
                return self.getmsg(code=999,locale=locale_lower,data={'locale':locale,'code':code})
            else:
                return self.getmsg(code=999,data={'locale':locale,'code':code})
        else:
            if locale_lower in self.msg["998"]:
                return self.getmsg(code=998,locale=locale_lower,data={'locale':locale,'code':code})
            else:
                return self.getmsg(code=998,data={'locale':locale,'code':code})

    def add(self, code, messages):
        int_code = int(code)
        code_str = f"{int_code:03}"
        if code_str in self.msg:
            raise KeyError(f"Message with code {code_str} already exists")
        else:
            self.msg[code_str] = messages
            print(f"Message with code {code_str} added to messages")

def msg(messages_data=None):
    return MessagesContainer(messages_data)