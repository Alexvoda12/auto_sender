import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient, errors
from telethon.tl.functions.messages import ImportChatInviteRequest
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelegramGroupSender:
    """Клиент для работы с группами Telegram"""
    
    def __init__(self, api_id, api_hash, session_name='group_sender'):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.is_running = False
        
    async def connect(self):
        """Подключение к Telegram"""
        try:
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.info("Требуется авторизация...")
                await self.authorize()
            else:
                logger.info("Используем сохраненную сессию")
                
            me = await self.client.get_me()
            logger.info(f"Авторизован как: {me.username or me.first_name} (ID: {me.id})")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            return False
    
    async def authorize(self):
        """Авторизация"""
        print("\n" + "="*50)
        print("АВТОРИЗАЦИЯ")
        print("="*50)
        
        phone = input("Введите номер телефона (+79991234567): ")
        await self.client.send_code_request(phone)
        code = input("Введите код из Telegram: ")
        
        try:
            await self.client.sign_in(phone, code)
        except errors.SessionPasswordNeededError:
            password = input("Введите пароль двухфакторной аутентификации: ")
            await self.client.sign_in(password=password)
    
    async def resolve_chat_id(self, chat_id):
        """
        Правильное разрешение ID чата
        Возвращает entity для использования в отправке сообщений
        """
        try:
            # Метод 1: Прямой поиск по ID (работает для всех типов чатов)
            try:
                entity = await self.client.get_entity(chat_id)
                chat_name = entity.title if hasattr(entity, 'title') else (
                    f"{entity.first_name or ''} {entity.last_name or ''}".strip() 
                    if hasattr(entity, 'first_name') else str(chat_id)
                )
                logger.info(f"Найден чат: {chat_name}")
                return entity
            except ValueError:
                # Если не найден по прямому ID, пробуем другие методы
                pass
            
            # Метод 2: Поиск через диалоги (для случаев, когда прямой get_entity не работает)
            dialogs = await self.client.get_dialogs()
            for dialog in dialogs:
                if hasattr(dialog.entity, 'id') and dialog.entity.id == chat_id:
                    logger.info(f"Найден в диалогах: {dialog.name}")
                    return dialog.entity
            
            # Метод 3: Для username (если передан строковый username)
            if isinstance(chat_id, str) and not chat_id.startswith('-'):
                try:
                    entity = await self.client.get_entity(chat_id)
                    logger.info(f"Найден по username: {chat_id}")
                    return entity
                except:
                    pass
            
            logger.error(f"Не удалось найти чат с ID: {chat_id}")
            logger.info("Попробуйте:")
            logger.info("1. Убедитесь, что вы участник группы")
            logger.info("2. Используйте username группы (например, @groupname)")
            logger.info("3. Получите актуальный ID через опцию 'Получить список чатов'")
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка разрешения ID: {e}")
            return None
    
    async def get_all_chats(self):
        """Получение всех доступных чатов"""
        try:
            dialogs = await self.client.get_dialogs(limit=50)
            
            print("\n" + "="*60)
            print("ДОСТУПНЫЕ ЧАТЫ:")
            print("="*60)
            
            for i, dialog in enumerate(dialogs):
                chat = dialog.entity
                chat_type = "👤 Личный"
                
                if hasattr(chat, 'megagroup') and chat.megagroup:
                    chat_type = "👥 Супергруппа"
                elif hasattr(chat, 'gigagroup') and chat.gigagroup:
                    chat_type = "👥 Гигагруппа"
                elif hasattr(chat, 'broadcast'):
                    chat_type = "📢 Канал"
                elif hasattr(chat, 'title'):
                    chat_type = "💬 Группа"
                
                name = chat.title if hasattr(chat, 'title') else f"{chat.first_name or ''} {chat.last_name or ''}".strip()
                print(f"{i+1:2d}. {chat_type} | ID: {chat.id:15} | {name}")
            
            print("="*60)
            print("💡 Для отправки сообщения используйте ID из столбца 'ID'")
            print("="*60)
            return dialogs
            
        except Exception as e:
            logger.error(f"Ошибка получения чатов: {e}")
            return []
    
    async def join_group_by_link(self, invite_link):
        """Вступление в группу по ссылке-приглашению"""
        try:
            # Извлекаем hash из ссылки
            if 't.me/' in invite_link:
                hash_part = invite_link.split('/')[-1]
                if hash_part.startswith('+'):
                    hash_part = hash_part[1:]
            else:
                hash_part = invite_link
            
            result = await self.client(ImportChatInviteRequest(hash_part))
            logger.info(f"Успешно вступили в группу: {result.chats[0].title}")
            return result.chats[0].id
            
        except errors.UserAlreadyParticipantError:
            logger.info("Вы уже участник этой группы")
            return None
        except Exception as e:
            logger.error(f"Ошибка вступления в группу: {e}")
            return None
    
    async def send_to_group(self, group_id, message):
        """Отправка сообщения в группу"""
        try:
            # Прямая отправка через get_entity
            entity = await self.client.get_entity(group_id)
            result = await self.client.send_message(entity, message)
            
            group_name = entity.title if hasattr(entity, 'title') else f"ID: {group_id}"
            logger.info(f"✅ Сообщение отправлено в '{group_name}'")
            return result
            
        except errors.ChatWriteForbiddenError:
            logger.error("❌ Нет прав на отправку сообщений в эту группу")
        except errors.ChannelInvalidError:
            logger.error("❌ Неверный ID группы или вы не участник")
        except errors.FloodWaitError as e:
            logger.error(f"⏳ Лимит сообщений! Ждите {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
            return await self.send_to_group(group_id, message)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
        
        return None
    
    async def schedule_to_group(self, group_id, message, interval_minutes=1):
        """Планировщик отправки в группу"""
        self.is_running = True
        interval_seconds = interval_minutes * 60
        
        # Сначала проверяем доступ
        try:
            entity = await self.client.get_entity(group_id)
            if not entity:
                logger.error(f"Не удалось получить доступ к группе {group_id}")
                return
        except Exception as e:
            logger.error(f"Ошибка доступа к группе: {e}")
            return
        
        group_name = entity.title if hasattr(entity, 'title') else f"Группа {group_id}"
        
        print("\n" + "="*60)
        print("🚀 ЗАПУСК ОТПРАВКИ В ГРУППУ")
        print("="*60)
        print(f"Группа: {group_name}")
        print(f"ID: {group_id}")
        print(f"Сообщение: '{message}'")
        print(f"Интервал: {interval_minutes} минута(ы)")
        print("="*60)
        print("Нажмите Ctrl+C для остановки")
        print("="*60 + "\n")
        
        counter = 1
        
        try:
            while self.is_running:
                current_time = datetime.now().strftime("%H:%M:%S")
                
                # Формируем сообщение
                full_message = f"{message}\n\nСообщение #{counter}\nВремя: {current_time}"
                
                # Отправляем
                logger.info(f"[{current_time}] Отправка #{counter}...")
                result = await self.send_to_group(group_id, full_message)
                
                if result:
                    print(f"[{current_time}] ✅ #{counter} отправлено (ID: {result.id})")
                else:
                    print(f"[{current_time}] ❌ #{counter} не отправлено")
                
                counter += 1
                
                # Ожидание
                for remaining in range(interval_seconds, 0, -1):
                    if not self.is_running:
                        break
                    mins, secs = divmod(remaining, 60)
                    print(f"   Следующее сообщение через: {mins:02d}:{secs:02d}", end='\r')
                    await asyncio.sleep(1)
                
                print(" " * 50, end='\r')
                
        except KeyboardInterrupt:
            logger.info("Остановлено пользователем")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            self.is_running = False
    
    async def disconnect(self):
        """Отключение"""
        self.is_running = False
        await self.client.disconnect()
        logger.info("Отключено")


async def main():
    """Основная функция"""
    print("="*60)
    print("TELEGRAM GROUP SENDER")
    print("="*60)
    
    # Данные API
    api_id = '39646115' #input("API ID: ").strip()
    api_hash = '1029ed27588c4027797eaf3b0667e276' #input("API Hash: ").strip()
    
    if not api_id or not api_hash:
        print("❌ API данные обязательны!")
        return
    
    # Создаем клиент
    sender = TelegramGroupSender(api_id, api_hash)
    
    try:
        if await sender.connect():
            print("\n1. Получить список чатов")
            print("2. Вступить в группу по ссылке")
            print("3. Отправить сообщение в группу")
            print("4. Запустить периодическую отправку")
            
            choice = input("\nВыберите действие (1-4): ").strip()
            
            if choice == "1":
                await sender.get_all_chats()
                
            elif choice == "2":
                link = input("Введите ссылку-приглашение: ").strip()
                group_id = await sender.join_group_by_link(link)
                if group_id:
                    print(f"ID группы: {group_id}")
                
            elif choice == "3":
                group_input = input("Введите ID группы или username:(3669051362) ").strip() or '3669051362'
                message = input("Введите сообщение('/drink@BestPivo_bot'): ").strip()
                time_ = input("Введите время в секундах: ").strip() or 3600
                time_ = int(time_)
                print(f'Установлено время: {time_} секунд')
                # Определяем тип ввода (число или строка)
                try:
                    if group_input.startswith('-') or group_input.isdigit():
                        group_id = int(group_input)
                    else:
                        group_id = group_input  # оставляем как строку (username)
                        import time
                    while True:
                        # time.sleep(1)
                        await sender.send_to_group(group_id, message)
                        
                        await asyncio.sleep(time_)
                except ValueError:
                    print("❌ Неверный формат ID!")
                    
            elif choice == "4":
                group_input = input("Введите ID группы или username: ").strip()
                message = input("Введите сообщение (по умолчанию 'Привет!'): ").strip() or "Привет!"
                interval = input("Интервал в минутах (по умолчанию 1): ").strip()
                interval = int(interval) if interval.isdigit() else 1
                
                try:
                    if group_input.startswith('-') or group_input.isdigit():
                        group_id = int(group_input)
                    else:
                        group_id = group_input
                    
                    await sender.schedule_to_group(group_id, message, interval)
                except ValueError:
                    print("❌ Неверный формат ID!")
            else:
                print("Неверный выбор!")
                
    except KeyboardInterrupt:
        print("\nОстановлено")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        await sender.disconnect()


if __name__ == "__main__":
    # Убираем устаревшие настройки для Windows
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма завершена")
