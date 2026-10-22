"""MAFIA VOICE CONTROL V3 — The Boss Edition.

Windows desktop interface by MAFIA for a local/offline CS2 speech-to-chat engine.
This is real Qt UI (not a flattened mockup). No DLL injection, no Steam API or
memory access. CS2 send uses ordinary keyboard simulation and is best-effort.
"""
from __future__ import annotations

import math
import sys
import threading
from datetime import datetime
from pathlib import Path

import numpy as np
import psutil
import sounddevice as sd
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRectF, QSize, Slot
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from config_store import RESOURCES, CONFIG_PATH, load_config, save_config
from voice_engine import VoiceEngine
from speech_modes import ENGLISH_MODELS, MULTILINGUAL_MODELS, safe_mode

VERSION = '3.1.3'
C = {
    'base':'#07090D', 'surface':'#0D1118', 'panel':'#11151D', 'inner':'#151A23',
    'stroke':'#29303B', 'muted':'#91A0AE', 'white':'#F7F8FA', 'red':'#F32842',
    'red_bright':'#FF4A5F', 'green':'#29DCA1', 'gold':'#E2B78C',
}

STYLES = r'''
QWidget { font-family: 'Segoe UI', 'Arial'; font-size: 12px; color: #F7F8FA; background: transparent; }
QMainWindow, #root { background: #07090D; }
#sidebar { background: #0A0C11; border-right: 1px solid #222731; }
#topbar { background: #080B10; border-bottom: 1px solid #202731; }
#subtle { color: #8F9AA8; }
#overline { color: #E05F6D; font-size: 10px; font-weight: 800; letter-spacing: 2px; }
#title { font-size: 24px; font-weight: 800; color: white; }
#headline { font-size: 19px; font-weight: 800; }
#cardTitle { font-size: 12px; font-weight: 800; letter-spacing: 1px; }
#cardCaption { font-size: 11px; color: #92A0B1; }
#panel { background: #10141B; border: 1px solid #2A303A; border-radius: 15px; }
#inner { background: #151920; border: 1px solid #2A303A; border-radius: 11px; }
#nav { color: #B4BDC9; border: 1px solid transparent; border-radius: 10px; text-align: left; padding: 12px 15px; font-weight: 700; font-size: 12px; }
#nav:hover { background: #171D26; color: #FFFFFF; }
#nav:checked { background: #4B0C18; color: #FFFFFF; border: 1px solid #CF1C35; }
#action { background: #D71F36; border: 1px solid #FF4057; color: #FFFFFF; padding: 12px 16px; border-radius: 10px; font-weight: 800; }
#action:hover { background: #EF2943; }
#action:disabled { background: #492831; color: #9C8990; border-color: #62404A; }
#button { background: #1A2029; color: #F0F3F8; border: 1px solid #37414F; padding: 10px 13px; border-radius: 10px; font-weight: 700; }
#button:hover { border: 1px solid #F32842; background: #29232B; }
#button:disabled { background: #151820; color: #666F7A; border-color: #242935; }
#mode { background: #11151D; border: 1px solid #303845; border-radius: 9px; padding: 10px 14px; font-weight: 700; color: #A3AFBC; }
#mode:checked { color: #FFFFFF; background: #55101D; border: 1px solid #F32842; }
#mode:hover { color: #FFFFFF; }
#keyButton { color: #FFFFFF; background: #262D38; border: 1px solid #58606D; border-radius: 7px; font-weight: 800; padding: 6px 8px; min-width: 80px; }
#keyButton:hover { background: #4F1724; border-color: #F32842; }
#pill { border: 1px solid #60303A; background: #27131B; color: #F2A2AB; border-radius: 9px; padding: 8px 12px; font-weight: 700; font-size: 11px; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox { background: #171D26; color: white; border: 1px solid #3A4451; border-radius: 9px; min-height: 29px; padding: 5px 11px; }
QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #B7364A; }
QComboBox::drop-down { border: none; width: 25px; }
QComboBox QAbstractItemView { background: #181E26; color: #EEEEEE; border: 1px solid #5B303A; selection-background-color: #5A1B2A; }
QListWidget { border: 0; background: transparent; outline: none; }
QListWidget::item { padding: 9px; color: #CED5DF; border-bottom: 1px solid #252B35; }
QListWidget::item:hover { background: #1C2630; }
QListWidget::item:selected { background: #311722; border: 1px solid #682D3C; }
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: #11151C; border-radius: 5px; width: 9px; }
QScrollBar::handle:vertical { background: #505463; border-radius: 5px; min-height: 35px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QCheckBox { spacing: 9px; color: #D8DFE9; padding: 4px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QCheckBox::indicator:unchecked { border: 1px solid #596472; background: #171D26; border-radius: 5px; }
QCheckBox::indicator:checked { border: 1px solid #FF5369; background: #DB243B; border-radius: 5px; }
QToolTip { background: #26131B; color: white; border: 1px solid #D32A43; padding: 7px; }
QDialog { background: #0E1219; }
'''


def txt(s: str, name='', size=0, bold=False, wrap=False, alignment=None) -> QLabel:
    w = QLabel(s)
    if name: w.setObjectName(name)
    if size or bold:
        f = w.font()
        if size: f.setPointSize(size)
        if bold: f.setBold(True)
        w.setFont(f)
    w.setWordWrap(wrap)
    if alignment is not None: w.setAlignment(alignment)
    return w


def vert(parent=None, gap=10, margins=(0,0,0,0)):
    if isinstance(parent, (int, float)):
        gap, parent = int(parent), None
    a = QVBoxLayout(parent); a.setContentsMargins(*margins); a.setSpacing(gap); return a


def horiz(parent=None, gap=10, margins=(0,0,0,0)):
    if isinstance(parent, (int, float)):
        gap, parent = int(parent), None
    a = QHBoxLayout(parent); a.setContentsMargins(*margins); a.setSpacing(gap); return a


def frame(name='panel'):
    f=QFrame(); f.setObjectName(name); return f


def push(s, primary=False):
    b = QPushButton(s)
    b.setObjectName('action' if primary else 'button')
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setMinimumHeight(41)
    return b


def card(title, subtitle=None):
    f = frame(); v=vert(f,12,(16,15,16,15))
    v.addWidget(txt(title,'cardTitle'))
    if subtitle: v.addWidget(txt(subtitle,'cardCaption',wrap=True))
    return f,v


def divider_line():
    line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet('QFrame { background:#29313B; color:#29313B; max-height:1px; border:0; }')
    return line


class CinematicHeader(QWidget):
    """Cinematic artwork is only the header. Every control is an actual widget."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(207)
        self.image=QPixmap(str(RESOURCES/'assets'/'mafia_cinematic_header.jpg'))
        self.t=0
        self.tick=QTimer(self); self.tick.timeout.connect(self.animate); self.tick.start(100)

    def animate(self):
        self.t+=1
        if self.isVisible(): self.update()

    def paintEvent(self, e):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height()
        path=QPainterPath(); path.addRoundedRect(QRectF(1,1,w-2,h-2),15,15)
        p.setClipPath(path)
        if not self.image.isNull():
            iw,ih=self.image.width(),self.image.height()
            scale=max(w/iw,h/ih)
            ww,hh=iw*scale,ih*scale
            p.drawPixmap(QRectF((w-ww)/2,(h-hh)/2,ww,hh),self.image,QRectF(self.image.rect()))
        else:
            p.fillRect(self.rect(),QColor('#230D15'))
        grad=QLinearGradient(0,h-60,0,h)
        grad.setColorAt(0,QColor(4,7,12,0)); grad.setColorAt(1,QColor(4,7,12,240))
        p.fillRect(self.rect(),QBrush(grad))
        p.setClipping(False)
        p.setPen(QPen(QColor('#90313A'),1))
        p.drawRoundedRect(QRectF(1,1,w-2,h-2),15,15)
        x=20+(self.t*6)%(max(w-35,36))
        glow=QColor('#F32842'); glow.setAlpha(170)
        p.setPen(QPen(glow,3))
        p.drawLine(int(x),h-3,int(min(x+46,w-15)),h-3)
        p.end()


class VoiceCore(QWidget):
    clicked=Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(326)
        self.setMinimumWidth(320)
        self.status='OFFLINE'; self.level=0.; self.anim=0.
        self.ptt='F8'
        self.setToolTip('Click to enable or disable the voice listener.')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        timer=QTimer(self); timer.timeout.connect(self._tick); timer.start(50)
        self.timer=timer

    def _tick(self):
        self.anim+=0.067
        if self.status != 'RECORDING': self.level *= .9
        if self.isVisible(): self.update()

    def mouseReleaseEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def set_status(self, s):
        self.status=s; self.update()

    def set_level(self, l):
        self.level = max(0., min(1., float(l))); self.update()

    def set_ptt(self, k):
        self.ptt=k.upper(); self.update()

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height(); cx=w/2; cy=h*.448
        active=self.status in ('RECORDING','PROCESSING')
        operational=self.status in ('READY','RECORDING','PROCESSING')
        red=QColor('#F32842') if operational else QColor('#702C3B')
        # Dark brushed console background with subtle frequency grid
        grad=QLinearGradient(0,0,w,h)
        grad.setColorAt(0,QColor('#161A22')); grad.setColorAt(.6,QColor('#080B11')); grad.setColorAt(1,QColor('#131018'))
        p.setBrush(QBrush(grad)); p.setPen(QPen(QColor('#36404B'),1)); p.drawRoundedRect(QRectF(1,1,w-2,h-2),15,15)
        p.setPen(QPen(QColor(69,77,88,29),1))
        for x in range(22,w,26): p.drawLine(x,18,x,h-17)
        for y in range(18,h,26): p.drawLine(15,y,w-15,y)
        radius=min(w*.225, h*.325,112)
        # Live side equalizer bars: based on actual measured microphone volume while recording
        p.setPen(Qt.PenStyle.NoPen)
        for side in (-1,1):
            for i in range(17):
                x=cx+side*(radius+19+i*8)
                if x<15 or x>w-15: continue
                vib=.16+.84*abs(math.sin(i*.53+self.anim*2.2))
                height=(3+(self.level*65 if active else 5)*vib)
                col=QColor('#F82B47') if active else QColor('#4A252F')
                col.setAlpha(int(240-max(0,i-3)*9) if active else 140)
                p.setBrush(QBrush(col))
                p.drawRoundedRect(QRectF(x-1.5,cy-height/2,3,height),1.5,1.5)
        # Orb diffuse outer halo and rotating tick ring
        for layer in range(5,0,-1):
            color=QColor(red); color.setAlpha((23 if operational else 12)*(6-layer))
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(color,layer*5))
            size=radius+12+layer*2+(self.level*9 if active else 0)
            p.drawEllipse(QRectF(cx-size,cy-size,size*2,size*2))
        p.setPen(QPen(QColor('#522834'),11)); p.setBrush(QBrush(QColor('#08090C')))
        p.drawEllipse(QRectF(cx-radius,cy-radius,radius*2,radius*2))
        p.setPen(QPen(red,4)); p.drawEllipse(QRectF(cx-radius,cy-radius,radius*2,radius*2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor('#FF5E70') if operational else QColor('#704353'),3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        for i in range(5):
            offset=self.anim*(40 if operational else 10)
            p.drawArc(QRectF(cx-radius+11,cy-radius+11,(radius-11)*2,(radius-11)*2),int((i*72+offset)*16),int(33*16))
        inner=radius*.81
        radial=QRadialGradient(cx,cy,inner)
        radial.setColorAt(0,QColor('#4B1520') if operational else QColor('#211720'))
        radial.setColorAt(1,QColor('#0B0B10'))
        p.setPen(QPen(QColor('#72313D'),1)); p.setBrush(QBrush(radial))
        p.drawEllipse(QRectF(cx-inner,cy-inner,inner*2,inner*2))
        # vector mic icon, not an image button
        mr=max(12,radius*.15); mh=mr*2.5
        p.setBrush(QBrush(QColor('#FAF7F8'))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(cx-mr,cy-mh*.72,mr*2,mh),mr,mr)
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor('#FAF7F8'),4,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(cx-mr*1.55,cy-mr*.9,mr*3.1,mr*3.3),180*16,180*16)
        p.drawLine(int(cx),int(cy+mr*1.6),int(cx),int(cy+mr*2.1))
        p.drawLine(int(cx-mr),int(cy+mr*2.1),int(cx+mr),int(cy+mr*2.1))
        # crown on top of the mic
        p.setPen(QPen(QColor('#FF4C61'),2))
        bx,by=cx,cy-radius*.52
        poly=[(bx-13,by),(bx-11,by-14),(bx-3,by-5),(bx,by-18),(bx+4,by-5),(bx+12,by-14),(bx+13,by)]
        for a,b in zip(poly,poly[1:]): p.drawLine(int(a[0]),int(a[1]),int(b[0]),int(b[1]))
        p.drawLine(int(bx-13),int(by+3),int(bx+13),int(by+3))
        # text field (distinct from graphic background)
        statuses={'OFFLINE':'SYSTEM OFFLINE','LOADING':'LOADING AI MODEL','DOWNLOADING':'DOWNLOADING AI MODEL',
                  'READY':'HOLD TO SPEAK','RECORDING':'LISTENING...','PROCESSING':'TRANSCRIBING...','ERROR':'CHECK STATUS'}
        status=statuses.get(self.status,self.status)
        f=QFont('Segoe UI',11); f.setBold(True); p.setFont(f)
        p.setPen(QColor('#FF596E') if operational else QColor('#9D8991'))
        p.drawText(QRectF(10,h-83,w-20,22),Qt.AlignmentFlag.AlignCenter,status)
        p.setFont(QFont('Segoe UI',10)); p.setPen(QColor('#9FAAB7'))
        p.drawText(QRectF(10,h-56,w-20,24),Qt.AlignmentFlag.AlignCenter,
                   f'Push-to-talk: {self.ptt}    |    CS2 local voice-to-chat')
        p.end()


class KeyCapture(QDialog):
    """No text configuration editing required for common keyboard and mouse hotkeys."""
    def __init__(self, current, parent=None):
        super().__init__(parent)
        self.value=None
        self.setWindowTitle('MAFIA — Bind Key')
        self.setModal(True)
        self.setFixedSize(395,170)
        v=vert(self,15,(22,20,22,20))
        v.addWidget(txt('PRESS YOUR NEW KEY',size=16,bold=True))
        v.addWidget(txt('Keyboard: F1–F12, letters or digits.\nMouse: press a side button (Mouse 4 / Mouse 5).', 'cardCaption', wrap=True))
        v.addWidget(txt('Current bind: '+current.upper(), 'overline'))
        cancel=push('CANCEL'); cancel.clicked.connect(self.reject); v.addWidget(cancel)

    def keyPressEvent(self, e):
        key=e.key()
        if key==Qt.Key.Key_Escape: self.reject(); return
        mapping={Qt.Key.Key_Space:'space',Qt.Key.Key_Tab:'tab',Qt.Key.Key_Insert:'insert',
                 Qt.Key.Key_Home:'home',Qt.Key.Key_End:'end'}
        if key in mapping: result=mapping[key]
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
            result=f'f{int(key)-int(Qt.Key.Key_F1)+1}'
        elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            result=chr(ord('a')+int(key)-int(Qt.Key.Key_A))
        elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            result=chr(ord('0')+int(key)-int(Qt.Key.Key_0))
        else: return
        self.value=result; self.accept()

    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.XButton1: self.value='mouse4'; self.accept(); return
        if e.button()==Qt.MouseButton.XButton2: self.value='mouse5'; self.accept(); return
        super().mousePressEvent(e)


class UiEvents(QObject):
    mic_result=Signal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config=load_config()
        self.engine=VoiceEngine(self.config,self)
        self.events=UiEvents()
        self.events.mic_result.connect(self._on_mic_test_result)
        self.engine.status_changed.connect(self.on_status)
        self.engine.level_changed.connect(self.on_level)
        self.engine.heard.connect(self.on_heard)
        self.engine.event.connect(self.on_event)
        self.engine.mode_changed.connect(self.on_mode)
        self.state='OFFLINE'; self._quitting=False; self._last_row=None
        self.setWindowTitle('MAFIA VOICE CONTROL V3.1.2 | THE BOSS EDITION | Created by MAFIA')
        self.app_icon=QIcon(str(RESOURCES/'assets'/'mafia_voice.ico'))
        self.setWindowIcon(self.app_icon)
        self.setMinimumSize(1020,690); self.resize(1390,875)
        self.build_ui(); self.setup_tray(); self.on_status('OFFLINE')
        game_timer=QTimer(self); game_timer.timeout.connect(self.refresh_game_status)
        game_timer.start(2300); self.game_timer=game_timer
        self.refresh_game_status()

    def build_ui(self):
        root=QWidget(); root.setObjectName('root'); self.setCentralWidget(root)
        outer=horiz(root,0)
        self.sidebar=frame('sidebar'); self.sidebar.setFixedWidth(204)
        outer.addWidget(self.sidebar)
        left=vert(self.sidebar,11,(13,20,13,14))
        logo=txt('♛  MAFIA',size=22,bold=True)
        logo.setStyleSheet('color:#F4F5F7; font-family: Georgia; font-weight:900;')
        left.addWidget(logo)
        left.addWidget(txt('VOICE CONTROL  /  V3',name='overline'))
        left.addSpacing(15)
        left.addWidget(txt('CONTROL CENTER',name='cardCaption'))
        self.navigation=[]
        for position,(name,idx) in enumerate([('⌂   HOME',0),('◉   VOICE CONTROL',0),('⌨   KEYBINDS',1),('⚙   SETTINGS',1),('◆   ABOUT MAFIA',2)]):
            b=push(name); b.setObjectName('nav'); b.setCheckable(True); b.setMinimumHeight(45)
            b.clicked.connect(lambda checked, page=idx, pos=position: self.go(page,pos))
            left.addWidget(b); self.navigation.append((b,idx))
        left.addStretch(1)
        brand_photo=QLabel(); brand_photo.setAlignment(Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignHCenter)
        art=QPixmap(str(RESOURCES/'assets'/'boss_signature.jpg'))
        if not art.isNull(): brand_photo.setPixmap(art.scaled(177,228,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation))
        brand_photo.setFixedHeight(228)
        brand_photo.setStyleSheet('border-radius:13px; background:#100F13;')
        left.addWidget(brand_photo)
        left.addWidget(txt('THE BOSS EDITION',name='overline',alignment=Qt.AlignmentFlag.AlignCenter))
        left.addWidget(txt('CREATED BY MAFIA',name='cardCaption',alignment=Qt.AlignmentFlag.AlignCenter))
        right=QWidget(); r=vert(right,0); outer.addWidget(right,1)
        top=frame('topbar'); top.setFixedHeight(60)
        tb=horiz(top,10,(22,0,22,0))
        tb.addWidget(txt('MAFIA / COMMAND CENTER',size=12,bold=True))
        tb.addStretch(1)
        self.game_pill=txt('● CS2: CHECKING','pill')
        self.app_pill=txt('● LISTENER OFFLINE','pill')
        tb.addWidget(self.game_pill); tb.addWidget(self.app_pill)
        r.addWidget(top)
        self.stack=QStackedWidget(); r.addWidget(self.stack,1)
        self.build_home(); self.build_settings(); self.build_about()
        self.go(0)

    def scrolled_page(self):
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        canvas=QWidget(); lay=vert(canvas,17,(20,18,20,22))
        scroll.setWidget(canvas)
        return scroll,lay

    def build_home(self):
        scroll,v=self.scrolled_page()
        self.stack.addWidget(scroll)
        v.addWidget(CinematicHeader())
        labelrow=horiz()
        labelrow.addWidget(txt('YOUR VOICE. YOUR RULES.',size=15,bold=True))
        labelrow.addStretch()
        labelrow.addWidget(txt('LOCAL • ENGLISH + ARABIC TRANSLATION • CS2','overline'))
        v.addLayout(labelrow)
        controls=horiz(gap=15)
        maincol=vert(gap=12)
        self.orb=VoiceCore(); self.orb.clicked.connect(self.toggle_listener)
        maincol.addWidget(self.orb)
        row=horiz(gap=10)
        self.active_btn=push('ACTIVATE VOICE SYSTEM',True)
        self.active_btn.clicked.connect(self.toggle_listener)
        row.addWidget(self.active_btn,4)
        self.test_btn=push('TEST MICROPHONE')
        self.test_btn.clicked.connect(self.test_microphone)
        row.addWidget(self.test_btn,3)
        maincol.addLayout(row)
        self.feedback=txt('Listener is offline. Activate it, then hold the hotkey in CS2.', 'cardCaption', wrap=True)
        maincol.addWidget(self.feedback)
        controls.addLayout(maincol,5)
        side=vert(gap=11)
        device_box,db=card('◖  MICROPHONE INPUT')
        devrow=horiz(gap=7)
        self.device_combo=QComboBox(); devrow.addWidget(self.device_combo,1)
        refresh=push('↻'); refresh.setFixedWidth(42); refresh.clicked.connect(self.load_devices)
        devrow.addWidget(refresh); db.addLayout(devrow)
        self.mic_info=txt('Select your audio input.', 'cardCaption'); db.addWidget(self.mic_info)
        self.device_combo.currentIndexChanged.connect(self.device_changed)
        side.addWidget(device_box)
        lang_box,lang_layout=card('✧  SPEECH TRANSLATION')
        lang_layout.addWidget(txt('WHAT LANGUAGE ARE YOU SPEAKING?',name='overline'))
        self.speech_mode_home=QComboBox()
        self.add_speech_mode_options(self.speech_mode_home)
        self.speech_mode_home.currentIndexChanged.connect(self.change_speech_mode_home)
        lang_layout.addWidget(self.speech_mode_home)
        self.speech_mode_tip=txt('English speech → English CS2 chat.',name='cardCaption',wrap=True)
        lang_layout.addWidget(self.speech_mode_tip)
        self.speech_test_btn=push('TEST SPEECH TRANSLATION (4.5s)')
        self.speech_test_btn.clicked.connect(self.test_speech_translation)
        lang_layout.addWidget(self.speech_test_btn)
        self.speech_test_result=txt('Speech test works outside CS2. It never sends game chat.',name='cardCaption',wrap=True)
        self.speech_test_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lang_layout.addWidget(self.speech_test_result)
        side.addWidget(lang_box)
        chat_box,cb=card('◫  CHAT DESTINATION')
        chatter=horiz(gap=8)
        self.team_btn=push('TEAM CHAT'); self.team_btn.setObjectName('mode'); self.team_btn.setCheckable(True)
        self.all_btn=push('ALL CHAT'); self.all_btn.setObjectName('mode'); self.all_btn.setCheckable(True)
        self.team_btn.clicked.connect(lambda: self.engine.set_mode(True))
        self.all_btn.clicked.connect(lambda: self.engine.set_mode(False))
        chatter.addWidget(self.team_btn); chatter.addWidget(self.all_btn)
        cb.addLayout(chatter)
        cb.addWidget(txt('Target channel for the next recognized message.', 'cardCaption',wrap=True))
        side.addWidget(chat_box)
        status_box,sb=card('◉  VOICE STATUS')
        self.status_text=txt('OFFLINE',size=19,bold=True)
        sb.addWidget(self.status_text)
        self.status_description=txt('Model is not running.',name='cardCaption',wrap=True)
        sb.addWidget(self.status_description)
        sb.addWidget(divider_line())
        self.mic_meter=txt('INPUT  ▏░░░░░░░░░░░░░░░░░░',name='cardCaption')
        sb.addWidget(self.mic_meter)
        side.addWidget(status_box)
        side.addStretch(1)
        controls.addLayout(side,3)
        v.addLayout(controls)
        lower=horiz(gap=15)
        log,lv=card('▤  RECENT PHRASES', 'Session-only transcript history. Sending status is best-effort, not a CS2 confirmation.')
        self.phrases=QListWidget(); self.phrases.setMinimumHeight(195)
        lv.addWidget(self.phrases)
        clear=push('CLEAR HISTORY'); clear.clicked.connect(self.clear_history)
        lv.addWidget(clear)
        lower.addWidget(log,5)
        binds,bv=card('⌨  KEYBIND CONTROL', 'Click any key to reassign it without opening a Python file.')
        bind1=horiz(); bind1.addWidget(txt('Push to talk (hold)',name='cardCaption'));bind1.addStretch()
        self.ptt_btn=push('F8');self.ptt_btn.setObjectName('keyButton'); self.ptt_btn.clicked.connect(lambda:self.capture_key('push_to_talk_key'))
        bind1.addWidget(self.ptt_btn); bv.addLayout(bind1)
        bind2=horiz(); bind2.addWidget(txt('Switch team / all',name='cardCaption'));bind2.addStretch()
        self.mode_key_btn=push('F9');self.mode_key_btn.setObjectName('keyButton'); self.mode_key_btn.clicked.connect(lambda:self.capture_key('toggle_chat_key'))
        bind2.addWidget(self.mode_key_btn); bv.addLayout(bind2)
        bv.addWidget(divider_line())
        self.info_line=txt('No injection • Offline Whisper • English / Arabic → English','cardCaption',wrap=True)
        bv.addWidget(self.info_line)
        bv.addStretch()
        lower.addWidget(binds,4)
        v.addLayout(lower)
        footer=horiz()
        footer.addWidget(txt('MAFIA ORIGINAL EDITION   /   THE BOSS COLLECTION',name='overline'))
        footer.addStretch()
        footer.addWidget(txt(f'CREATED BY MAFIA  •  {VERSION}',name='cardCaption'))
        v.addLayout(footer)
        self.load_devices()
        self.on_mode(self.config.get('team_only',True))
        self.refresh_key_labels()

    def build_settings(self):
        scroll,v=self.scrolled_page(); self.stack.addWidget(scroll)
        v.addWidget(txt('CONTROL CONFIGURATION',size=27,bold=True))
        v.addWidget(txt('Fine tune your local CS2 voice-to-text engine. Changes save automatically.',name='cardCaption'))
        row=horiz(gap=15)
        behavior,b=card('AUTOMATION & GAME CHAT')
        self.auto_check=QCheckBox('Auto-send recognized messages to CS2')
        self.auto_check.setChecked(bool(self.config.get('auto_send',True)))
        self.auto_check.toggled.connect(lambda val:self.update_config('auto_send',val))
        b.addWidget(self.auto_check)
        self.tray_check=QCheckBox('Keep running in the Windows system tray')
        self.tray_check.setChecked(bool(self.config.get('minimize_to_tray',True)))
        self.tray_check.toggled.connect(lambda val:self.update_config('minimize_to_tray',val))
        b.addWidget(self.tray_check)
        b.addWidget(divider_line())
        b.addWidget(txt('CS2 TEAM CHAT KEY',name='overline'))
        self.team_key=QLineEdit(str(self.config.get('team_chat_key','u')))
        self.team_key.setMaxLength(1);self.team_key.setToolTip('Match your CS2 team-chat keybind, usually U')
        self.team_key.editingFinished.connect(lambda:self.save_chat_key('team_chat_key',self.team_key))
        b.addWidget(self.team_key)
        b.addWidget(txt('CS2 ALL CHAT KEY',name='overline'))
        self.all_key=QLineEdit(str(self.config.get('all_chat_key','y')))
        self.all_key.setMaxLength(1);self.all_key.setToolTip('Match your CS2 all-chat keybind, usually Y')
        self.all_key.editingFinished.connect(lambda:self.save_chat_key('all_chat_key',self.all_key))
        b.addWidget(self.all_key)
        b.addStretch()
        row.addWidget(behavior,1)
        speech,s=card('LOCAL SPEECH ENGINE')
        s.addWidget(txt('SPEECH LANGUAGE / TRANSLATION',name='overline'))
        self.speech_mode_settings=QComboBox()
        self.add_speech_mode_options(self.speech_mode_settings)
        self.speech_mode_settings.currentIndexChanged.connect(self.change_speech_mode_settings)
        s.addWidget(self.speech_mode_settings)
        s.addWidget(txt('Arabic mode first transcribes your Arabic words, then uses CS2 callouts or optional offline Argos translator. For general Arabic, run INSTALL_TRANSLATOR.bat once.',name='cardCaption',wrap=True))
        s.addWidget(txt('WHISPER MODEL',name='overline'))
        self.model=QComboBox()
        self.model.currentTextChanged.connect(self.change_speech_model)
        s.addWidget(self.model)
        self.model_tip=txt('Larger models improve Arabic accuracy but can use more CPU/RAM and load slowly.',name='cardCaption',wrap=True)
        s.addWidget(self.model_tip)
        self.refresh_speech_controls()
        s.addWidget(txt('MAX RECORDING SECONDS',name='overline'))
        self.max_s=QSpinBox();self.max_s.setRange(2,30);self.max_s.setValue(int(self.config.get('max_seconds',8)))
        self.max_s.valueChanged.connect(lambda x:self.update_config('max_seconds',x))
        s.addWidget(self.max_s)
        s.addWidget(txt('SILENCE THRESHOLD (RMS)',name='overline'))
        self.silence=QDoubleSpinBox();self.silence.setDecimals(3);self.silence.setSingleStep(.002)
        self.silence.setRange(0.0,.150);self.silence.setValue(float(self.config.get('silence_rms',.006)))
        self.silence.valueChanged.connect(lambda x:self.update_config('silence_rms',x))
        s.addWidget(self.silence)
        s.addStretch()
        row.addWidget(speech,1)
        v.addLayout(row)
        extras,ex=card('ADVANCED SEND OPTIONS')
        r=horiz()
        inner=vert()
        inner.addWidget(txt('MAX MESSAGE CHARACTERS',name='overline'))
        self.max_chars=QSpinBox();self.max_chars.setRange(20,255)
        self.max_chars.setValue(int(self.config.get('max_chars',110)))
        self.max_chars.valueChanged.connect(lambda x:self.update_config('max_chars',x))
        inner.addWidget(self.max_chars);r.addLayout(inner)
        inner=vert()
        inner.addWidget(txt('CHAT OPEN DELAY (SECONDS)',name='overline'))
        self.open_delay=QDoubleSpinBox();self.open_delay.setRange(.10,1.20);self.open_delay.setSingleStep(.05)
        self.open_delay.setValue(float(self.config.get('chat_open_delay',.22)))
        self.open_delay.valueChanged.connect(lambda x:self.update_config('chat_open_delay',x))
        inner.addWidget(self.open_delay);r.addLayout(inner)
        inner=vert()
        inner.addWidget(txt('TYPING INTERVAL (SECONDS)',name='overline'))
        self.typing=QDoubleSpinBox();self.typing.setDecimals(3);self.typing.setSingleStep(.005)
        self.typing.setRange(.001,.10);self.typing.setValue(float(self.config.get('type_interval',.012)))
        self.typing.valueChanged.connect(lambda x:self.update_config('type_interval',x))
        inner.addWidget(self.typing);r.addLayout(inner)
        ex.addLayout(r)
        ex.addWidget(txt('Keep these defaults unless CS2 misses the chat opening or some keystrokes.',name='cardCaption'))
        v.addWidget(extras)
        actions=horiz()
        openfolder=push('OPEN SETTINGS FOLDER');openfolder.clicked.connect(self.show_config_path)
        actions.addWidget(openfolder);actions.addStretch()
        actions.addWidget(txt('CHANGES SAVED AUTOMATICALLY',name='overline'))
        v.addLayout(actions);v.addStretch(1)

    def build_about(self):
        scroll,v=self.scrolled_page();self.stack.addWidget(scroll)
        v.addWidget(CinematicHeader())
        v.addWidget(txt('MAFIA VOICE CONTROL',size=29,bold=True))
        v.addWidget(txt('V3 — THE BOSS EDITION  •  CREATED BY MAFIA',name='overline'))
        about,content=card('BUILT FOR THE GAME. SIGNED BY MAFIA.')
        content.addWidget(txt('A fully local Windows voice-to-chat controller for Counter-Strike 2. Speak in English, or recognize Arabic locally and translate CS2 callouts into English. Optional Argos provides offline general-sentence translation.',name='cardCaption',wrap=True))
        content.addWidget(divider_line())
        content.addWidget(txt('PRIVACY: Speech audio is processed locally. A model may download on first use. Voice history is not saved to disk.','cardCaption',wrap=True))
        content.addWidget(txt('INTEGRATION: Uses normal OS input simulation only, not game memory, anti-cheat bypasses, injected modules, or Steam APIs. Automatic chat delivery is not guaranteed and should be tested carefully.','cardCaption',wrap=True))
        content.addWidget(txt('VISUAL IDENTITY: Cyber-noir cinema, red neon, the MAFIA insignia, and your original Created by MAFIA signature.','cardCaption',wrap=True))
        v.addWidget(about);v.addStretch(1)
        v.addWidget(txt(f'© MAFIA ORIGINAL EDITION     •     VERSION {VERSION}',name='overline'))

    def go(self,index,selected=None):
        self.stack.setCurrentIndex(index)
        if selected is None: selected={0:0,1:3,2:4}[index]
        for i,(nav,page) in enumerate(self.navigation):
            nav.blockSignals(True)
            nav.setChecked(i==selected)
            nav.blockSignals(False)

    def clear_history(self):
        self._last_row=None
        self.phrases.clear()

    @staticmethod
    def add_speech_mode_options(combo):
        combo.addItem('English speech  →  English chat', 'english')
        combo.addItem('Arabic speech  →  English chat', 'arabic_translate')

    def refresh_speech_controls(self):
        mode = safe_mode(self.config.get('speech_mode', 'english'))
        for name in ('speech_mode_home', 'speech_mode_settings'):
            combo = getattr(self, name, None)
            if combo is not None:
                combo.blockSignals(True)
                combo.setCurrentIndex(max(0, combo.findData(mode)))
                combo.blockSignals(False)
        model_combo = getattr(self, 'model', None)
        if model_combo is not None:
            model_combo.blockSignals(True)
            model_combo.clear()
            options = MULTILINGUAL_MODELS if mode == 'arabic_translate' else ENGLISH_MODELS
            model_combo.addItems(list(options))
            selected = str(self.config.get('model', 'base.en'))
            if selected not in options:
                selected = 'small' if mode == 'arabic_translate' else 'base.en'
            model_combo.setCurrentText(selected)
            model_combo.blockSignals(False)
        tip = getattr(self, 'speech_mode_tip', None)
        if tip is not None:
            tip.setText('Arabic recognition → CS2 callouts / optional offline translation. Unknown speech is NOT sent.'
                        if mode == 'arabic_translate' else 'English voice → English CS2 chat. Fast English-only model.')

    def change_speech_mode_home(self, index):
        self.change_speech_mode(self.speech_mode_home.itemData(index))

    def change_speech_mode_settings(self, index):
        self.change_speech_mode(self.speech_mode_settings.itemData(index))

    def change_speech_mode(self, new_mode):
        mode = safe_mode(new_mode)
        current = safe_mode(self.config.get('speech_mode', 'english'))
        if mode == current:
            return
        if self.state in ('RECORDING', 'PROCESSING', 'TESTING'):
            self.refresh_speech_controls()
            QMessageBox.information(self, 'MAFIA VOICE', 'Finish the current phrase before changing speech language.')
            return
        self.config['speech_mode'] = mode
        if mode == 'arabic_translate':
            self.config['model'] = str(self.config.get('arabic_model', 'small'))
        else:
            self.config['model'] = str(self.config.get('english_model', 'base.en'))
        save_config(self.config)
        self.refresh_speech_controls()
        if self.engine.enabled:
            self.engine.stop()
            self.engine.start()
        self.feedback.setText('Arabic → English translation selected. Model may download on first use.'
                              if mode == 'arabic_translate' else 'English voice mode selected.')

    def change_speech_model(self, model):
        mode = safe_mode(self.config.get('speech_mode', 'english'))
        options = MULTILINGUAL_MODELS if mode == 'arabic_translate' else ENGLISH_MODELS
        if model not in options or self.config.get('model') == model:
            return
        if self.state in ('RECORDING', 'PROCESSING', 'TESTING'):
            self.refresh_speech_controls()
            QMessageBox.information(self, 'MAFIA VOICE', 'Finish the current phrase before changing the model.')
            return
        self.config['model'] = model
        self.config['arabic_model' if mode == 'arabic_translate' else 'english_model'] = model
        save_config(self.config)
        if self.engine.enabled:
            self.engine.stop()
            self.engine.start()

    def load_devices(self):
        self.device_combo.blockSignals(True)
        self.device_combo.clear(); self.device_combo.addItem('Windows default microphone',None)
        try:
            for idx,d in enumerate(sd.query_devices()):
                if int(d['max_input_channels'])>0:
                    self.device_combo.addItem(f'{idx}  •  {d["name"]}',idx)
            current=self.config.get('microphone_device')
            loc=self.device_combo.findData(current)
            self.device_combo.setCurrentIndex(loc if loc>=0 else 0)
            self.mic_info.setText(f'{self.device_combo.count()-1} input device(s) detected')
        except Exception as exc:
            self.mic_info.setText(f'Could not list microphones: {exc}')
        self.device_combo.blockSignals(False)

    def device_changed(self,index):
        if index<0:return
        value=self.device_combo.itemData(index)
        self.update_config('microphone_device',value)

    def update_config(self,key,value,restart=False):
        if self.config.get(key)==value:return
        self.config[key]=value
        try: save_config(self.config)
        except OSError as exc:
            QMessageBox.warning(self,'Settings error',f'Could not save settings:\n{exc}')
        if restart and self.engine.enabled:
            self.engine.stop(); self.engine.start()

    def save_chat_key(self,name,edit):
        text=edit.text().strip().lower()
        if len(text)!=1 or not text.isascii() or not text.isalnum():
            QMessageBox.warning(self,'Invalid key','Use exactly one letter or digit, such as U or Y.')
            edit.setText(str(self.config.get(name,'u'))); return
        self.update_config(name,text)

    def capture_key(self,key):
        if self.state in ('RECORDING','PROCESSING','TESTING'):
            QMessageBox.information(self,'Busy','Finish the current recording before changing a key.')
            return
        dlg=KeyCapture(str(self.config.get(key,'')),self)
        if dlg.exec()!=QDialog.DialogCode.Accepted or not dlg.value: return
        other='toggle_chat_key' if key=='push_to_talk_key' else 'push_to_talk_key'
        if dlg.value==self.config.get(other):
            QMessageBox.warning(self,'Duplicate key','Push-to-talk and chat-mode hotkeys must differ.')
            return
        self.config[key]=dlg.value
        save_config(self.config)
        self.refresh_key_labels()
        if self.engine.enabled:
            self.engine.stop();self.engine.start()
        self.feedback.setText('Hotkey updated: '+dlg.value.upper())

    def refresh_key_labels(self):
        ptt=str(self.config.get('push_to_talk_key','f8')).upper()
        mode=str(self.config.get('toggle_chat_key','f9')).upper()
        self.ptt_btn.setText(ptt+'  ✎')
        self.mode_key_btn.setText(mode+'  ✎')
        self.orb.set_ptt(ptt)

    def toggle_listener(self):
        if self.engine.enabled:
            self.engine.stop()
        else:
            self.engine.start()

    @Slot(bool)
    def on_mode(self,team):
        self.team_btn.setChecked(bool(team)); self.all_btn.setChecked(not bool(team))

    @Slot(str)
    def on_status(self,status):
        self.state=status
        self.orb.set_status(status)
        descriptions={
            'OFFLINE':'Enable the engine to prepare your microphone hotkey.',
            'LOADING':'Loading the speech model from local storage into memory.',
            'DOWNLOADING':'First-time model download from Hugging Face. Audio stays on your PC.',
            'READY':'Ready. Focus CS2 and hold your push-to-talk key.',
            'RECORDING':'Microphone recording... release the key to transcribe.',
            'PROCESSING':('Recognizing Arabic, then translating locally...' if safe_mode(self.config.get('speech_mode'))=='arabic_translate' else 'Transcribing your phrase locally on this PC.'),
            'TESTING':'Independent microphone / translation test running. No message will be sent.',
            'ERROR':'Check the event line and START_DEBUG.bat if necessary.',
        }
        self.status_text.setText(status)
        self.speech_test_btn.setEnabled(status in ('READY',))
        self.status_text.setStyleSheet('color:'+('#30E0A1' if status=='READY' else '#F04459' if status in ('RECORDING','ERROR') else '#FFFFFF'))
        self.status_description.setText(descriptions.get(status,''))
        self.app_pill.setText('● '+('PREPARING MODEL' if status in ('LOADING','DOWNLOADING') else 'LISTENER ACTIVE' if self.engine.enabled else 'LISTENER OFFLINE'))
        self.app_pill.setStyleSheet('color:'+('#35DDA5' if self.engine.enabled else '#E99AA4')+';')
        self.active_btn.setText('DISABLE VOICE SYSTEM' if self.engine.enabled else 'ACTIVATE VOICE SYSTEM')
        self.feedback.setText(descriptions.get(status,''))

    @Slot(float)
    def on_level(self,l):
        self.orb.set_level(l)
        filled=int(max(0,min(1,l))*18)
        self.mic_meter.setText('INPUT  ▏'+'▮'*filled+'░'*(18-filled))

    @Slot(str)
    def on_heard(self,message):
        now=datetime.now().strftime('%H:%M:%S')
        item=QListWidgetItem(f'{now}   {message}\n          Recognized · preparing send')
        item.setData(Qt.ItemDataRole.UserRole,message)
        self.phrases.insertItem(0,item)
        self._last_row=item
        while self.phrases.count()>80: self.phrases.takeItem(self.phrases.count()-1)

    @Slot(str, str)
    def on_event(self,kind,message):
        if kind=='translation_trace':
            self.speech_test_result.setText(message)
            self.feedback.setText(message)
            self.info_line.setText(message[:105])
            return
        if kind=='translation_test':
            self.speech_test_result.setText(message)
            self.feedback.setText(message)
            self.info_line.setText(message[:105])
            return
        if kind=='attempted' and self._last_row:
            transcript=self._last_row.data(Qt.ItemDataRole.UserRole)
            self._last_row.setText(datetime.now().strftime('%H:%M:%S')+f'   {transcript}\n          Chat send attempted (not verified)')
        if kind in ('warning','error','preview'):
            self.feedback.setText(message)
            if kind in ('warning','error'):
                self.speech_test_result.setText('ENGINE: ' + message)
            if self._last_row and kind=='preview':
                transcript=self._last_row.data(Qt.ItemDataRole.UserRole)
                self._last_row.setText(datetime.now().strftime('%H:%M:%S')+f'   {transcript}\n          Preview only — not sent')
        elif kind=='info':
            self.info_line.setText(message[:105])

    def refresh_game_status(self):
        found=False
        try:
            found=any(p.info.get('name','').lower()=='cs2.exe' for p in psutil.process_iter(['name']))
        except (psutil.Error,OSError):pass
        self.game_pill.setText('● CS2 RUNNING' if found else '● CS2 NOT DETECTED')
        self.game_pill.setStyleSheet('color:'+('#37DFA2' if found else '#A2AAB4')+';')

    def test_speech_translation(self):
        self.engine.test_speech_translation()

    def test_microphone(self):
        if self.state in ('RECORDING','PROCESSING','TESTING'):
            self.feedback.setText('Finish current recording before microphone test.')
            return
        self.test_btn.setEnabled(False)
        self.feedback.setText('Recording a 2-second local microphone test...')
        device=self.config.get('microphone_device')
        def worker():
            try:
                details=sd.query_devices(device,'input')
                sr=int(details['default_samplerate'])
                recorded=sd.rec(int(sr*2.0),samplerate=sr,channels=1,dtype='float32',device=device)
                sd.wait()
                rms=float(np.sqrt(np.mean(recorded.astype('float64')**2)))
                peak=float(np.max(np.abs(recorded)))
                if rms<.002: msg='MIC TEST: very quiet or no input. Try a different microphone.'
                elif rms>.3 or peak>.98: msg='MIC TEST: input detected but loud/clipping. Lower mic gain.'
                else: msg=f'MIC TEST: signal OK! RMS {rms:.3f} | peak {peak:.2f}.'
            except Exception as exc:
                msg=f'MIC TEST FAILED: {type(exc).__name__}: {exc}'
            self.events.mic_result.emit(msg)
        threading.Thread(target=worker,daemon=True).start()

    @Slot(str)
    def _on_mic_test_result(self,msg):
        self.test_btn.setEnabled(True)
        self.feedback.setText(msg)

    def show_config_path(self):
        QMessageBox.information(self,'Settings path',f'Configuration is saved at:\n{CONFIG_PATH}')

    def setup_tray(self):
        self.tray=QSystemTrayIcon(self.app_icon,self)
        menu=QMenu(self)
        a=menu.addAction('Open MAFIA Voice Control')
        a.triggered.connect(self.bring_forward)
        b=menu.addAction('Enable / Disable Voice')
        b.triggered.connect(self.toggle_listener)
        menu.addSeparator()
        quit_action=menu.addAction('Exit Completely')
        quit_action.triggered.connect(self.quit_all)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason:self.bring_forward() if reason==QSystemTrayIcon.ActivationReason.DoubleClick else None)
        if QSystemTrayIcon.isSystemTrayAvailable():self.tray.show()

    def bring_forward(self):
        self.showNormal();self.raise_();self.activateWindow()

    def closeEvent(self,event):
        if not self._quitting and self.config.get('minimize_to_tray',True) and QSystemTrayIcon.isSystemTrayAvailable():
            self.hide();event.ignore();return
        self.engine.stop()
        event.accept()

    def quit_all(self):
        self._quitting=True
        self.engine.stop()
        self.tray.hide()
        self.close()
        QApplication.quit()


def main():
    app=QApplication(sys.argv)
    app.setApplicationName('MAFIA VOICE CONTROL V3')
    app.setOrganizationName('Created by MAFIA')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLES)
    app.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    win=MainWindow();win.show()
    sys.exit(app.exec())


if __name__=='__main__':
    main()
