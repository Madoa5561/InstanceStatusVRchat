import re
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
import socket
from pythonosc import udp_client
from pythonosc import osc_message_builder

class VRChatLogHandler(FileSystemEventHandler):
    def __init__(self):
        self.join_pattern = re.compile(r'\[Behaviour\] OnPlayerJoined (\S+) \(usr_\S+\)')
        self.leave_pattern = re.compile(r'\[Behaviour\] OnPlayerLeft (\S+)')
        self.instance_count_pattern = re.compile(r'\[Behaviour\] Hard max is (\d+)')
        self.world_pattern = re.compile(r'\[Behaviour\] Joining wrld_([a-f0-9\-]+):(\d+)~.*~region\((\w+)\)')
        self.last_position = 0
        self.joined_players = set()
        self.current_instance_count = 0
        self.current_instance_uuid = None
        self.ip = self.get_local_ip()
        self.port = 9000
        self.client = udp_client.SimpleUDPClient(self.ip, self.port)
        self.last_message_time = None
        self.last_join_player = None
        self.last_leave_player = None

    def get_local_ip(self):
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)

    def send_chatbox_message(self, text, bypass_keyboard=True, notify_sound=True):
        current_time = datetime.now()
        if self.last_message_time is None or (current_time - self.last_message_time).total_seconds() >= 10:
            message = osc_message_builder.OscMessageBuilder(address="/chatbox/input")
            message.add_arg(text)
            message.add_arg(bypass_keyboard)
            message.add_arg(notify_sound)
            osc_message = message.build()
            self.client.send(osc_message)
            self.last_message_time = current_time

    def on_modified(self, event):
        if not event.is_directory:
            try:
                with open(event.src_path, 'r', encoding='utf-8') as file:
                    file.seek(self.last_position)
                    for line in file:
                        line = line.strip()
                        join_match = self.join_pattern.search(line)
                        leave_match = self.leave_pattern.search(line)
                        instance_count_match = self.instance_count_pattern.search(line)
                        world_match = self.world_pattern.search(line)
                        if world_match:
                            uuid = world_match.group(1)
                            if self.current_instance_uuid != uuid:
                                self.current_instance_uuid = uuid
                                self.joined_players.clear()
                                print(f"インスタンスが変更されました:UUID: {self.current_instance_uuid}")
                        if join_match:
                            player_name = join_match.group(1).strip()
                            if player_name not in self.joined_players:
                                self.joined_players.add(player_name)
                                self.last_join_player = player_name
                                print(f"プレイヤーが参加しました: {player_name}")
                                print(f"{len(self.joined_players)}/{self.current_instance_count}")
                        if leave_match:
                            player_name = leave_match.group(1).strip()
                            if player_name in self.joined_players:
                                self.joined_players.remove(player_name)
                                self.last_leave_player = player_name
                                print(f"プレイヤーが退出しました: {player_name}")
                                print(f"{len(self.joined_players)}/{self.current_instance_count}")
                        if instance_count_match:
                            self.current_instance_count = int(instance_count_match.group(1))
                            print(f"インスタンスの最大人数: {self.current_instance_count}")
                    self.last_position = file.tell()
            except Exception as e:
                print(f"ログの解析中にエラーが発生しました: {e}")

    def display_player_count(self):
        current_count = len(self.joined_players)
        message = f"現在のインスタンス人数: {current_count}/{self.current_instance_count}\n👇最近参加したユーザー👇\n{self.last_join_player}\n👇最近退出したユーザー👇\n{self.last_leave_player}"
        self.send_chatbox_message(message)

def main():
    username = os.getlogin()
    log_dir = f"C:/Users/{username}/AppData/LocalLow/VRChat/VRChat"
    if not os.path.exists(log_dir):
        print(f"ログディレクトリが見つかりません: {log_dir}")
        return
    event_handler = VRChatLogHandler()
    observer = Observer()
    observer.schedule(event_handler, log_dir, recursive=False)
    observer.start()
    print(f"{log_dir} の監視を開始しました。Ctrl+Cで終了します")
    try:
        while True:
            time.sleep(10)
            event_handler.display_player_count()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
