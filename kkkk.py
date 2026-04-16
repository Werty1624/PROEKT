#pip install pyqt5
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton , QVBoxLayout
import random
app = QApplication([])#App
window = QWidget()
window.resize(400 , 400)
window.setWindowTitle('Number Gnerator')
label_winner = QLabel("Winner")
label_number = QLabel('?')
button_winner = QPushButton('Generate')
layout = QVBoxLayout()                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
layout.addWidget(label_winner)                                                                                          
layout.addWidget(label_number)
layout.addWidget(button_winner)

def generate_winner():
    number = random.randint(1, 100)
    label_number.setText(str(number))
    if number % 2 == 0:
        label_winner.setText('Машина')
    elif number % 3 == 0:
        label_winner.setText("house")
    else:
        label_winner.setText('Вы проиграли')


button_winner.clicked.connect(generate_winner)
window.setLayout(layout)
window.show()
app.exec()




