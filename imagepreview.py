
from PIL import ImageTk
import Queue
import Tkinter as tk

class ImagePreview:
  CLOSE_COMMAND = 'close'

  def __init__(self, size, img):
    self.size = size
    self.img = img

    self.msg_queue = Queue.Queue()

    self.root = tk.Tk()
    self.root.title('preview')

    tk_img = ImageTk.PhotoImage(self.img.resize(self.size))
    self.panel = tk.Label(self.root, image=tk_img)
    self.panel.pack(side='bottom', fill='both', expand='yes')
    self.panel.image = tk_img

  def start(self):
    self.root.after(50, self._update)
    self.root.mainloop()

  def receive(self, msg):
    self.msg_queue.put(msg)

  def _update(self):
    if not self.msg_queue.empty():
      msg = self.msg_queue.get()
      if msg == ImagePreview.CLOSE_COMMAND:
        self.root.destroy()
      else:
        self.img = msg
        tk_img = ImageTk.PhotoImage(self.img.resize(self.size))
        self.panel.configure(image=tk_img)
        self.panel.image = tk_img

    self.root.after(50, self._update)
