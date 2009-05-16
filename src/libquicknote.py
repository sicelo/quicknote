#/usr/bin/env python2.5
# -*- coding: utf-8 -*-

"""
 Copyright (C) 2007 Christoph Würstle

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License version 2 as
published by the Free Software Foundation.

@todo Add an edit menu with select all, cut, copy, and paste
@todo Add undo directly into the UI
@todo Add Note Export (txt File) and Export All (json dump?)
@todo Save word wrap and zoom setting 
"""


import os
import gc
import logging

import gtk

try:
	import hildon
	IS_HILDON = True
except ImportError:
	import fakehildon as hildon
	IS_HILDON = False

try:
	import osso
except ImportError:
	osso = None

import libspeichern
import libkopfzeile
import libnotizen
import libsync


try:
	_
except NameError:
	_ = lambda x: x


class quicknoteclass(hildon.Program):

	__pretty_app_name__ = "quicknote"
	__app_name__ = "quicknote"
	__version__ = "0.7.5"

	def __init__(self):
		super(quicknoteclass, self).__init__()

		home_dir = os.path.expanduser('~')
		dblog = os.path.join(home_dir, "quicknote.log")

		# define a Handler which writes INFO messages or higher to the sys.stderr
		console = logging.StreamHandler()
		console.setLevel(logging.DEBUG)
		# set a format which is simpler for console use
		formatter = logging.Formatter('%(asctime)s  %(levelname)-8s %(message)s')
		# tell the handler to use this format
		console.setFormatter(formatter)
		# add the handler to the root logger
		logging.getLogger('').addHandler(console)

		logging.info('Starting quicknote')

		if osso is not None:
			self._osso_c = osso.Context(self.__app_name__, self.__version__, False)
			self.device = osso.DeviceState(self._osso_c)
			self.device.set_device_state_callback(self._on_device_state_change, 0)
		else:
			self._osso_c = None

		#Get the Main Window, and connect the "destroy" event
		self.window = hildon.Window()
		self.add_window(self.window)

		self.window.set_title(self.__pretty_app_name__)
		self.window.connect("delete_event", self.delete_event)
		self.window.connect("destroy", self.destroy)
		self.window.connect("key-press-event", self.on_key_press)
		self.window.connect("window-state-event", self.on_window_state_change)
		self.window_in_fullscreen = False #The window isn't in full screen mode initially.

		self.db = libspeichern.Speichern()
		self.prepare_sync_dialog()

		#Create GUI main vbox
		vbox = gtk.VBox(homogeneous = False, spacing = 0)

		#Create Menu and apply it for hildon
		filemenu = gtk.Menu()

		menu_items = gtk.MenuItem(_("Set DB file"))
		filemenu.append(menu_items)
		menu_items.connect("activate", self.set_db_file, None)

		menu_items = gtk.MenuItem(_("SQL History"))
		filemenu.append(menu_items)
		menu_items.connect("activate", self.view_sql_history, None)

		menu_items = gtk.MenuItem(_("Sync notes"))
		filemenu.append(menu_items)
		menu_items.connect("activate", self.sync_notes, None)

		menu_items = gtk.MenuItem(_("Quit"))
		filemenu.append(menu_items)
		menu_items.connect("activate", self.destroy, None)

		file_menu = gtk.MenuItem(_("File"))
		file_menu.show()
		file_menu.set_submenu(filemenu)

		categorymenu = gtk.Menu()

		menu_items = gtk.MenuItem(_("delete"))
		categorymenu.append(menu_items)
		menu_items.connect("activate", self.delete_Category, None)

		menu_items = gtk.MenuItem(_("move to category"))
		categorymenu.append(menu_items)
		menu_items.connect("activate", self.move_Category, None)

		category_menu = gtk.MenuItem(_("Category"))
		category_menu.show()
		category_menu.set_submenu(categorymenu)

		viewmenu = gtk.Menu()

		menu_items = gtk.MenuItem(_("Word Wrap"))
		viewmenu.append(menu_items)
		menu_items.connect("activate", self.toggle_word_wrap, None)
		self._wordWrapEnabled = False

		view_menu = gtk.MenuItem(_("View"))
		view_menu.show()
		view_menu.set_submenu(viewmenu)

		helpmenu = gtk.Menu()

		menu_items = gtk.MenuItem(_("About"))
		helpmenu.append(menu_items)
		menu_items.connect("activate", self.show_about, None)

		help_menu = gtk.MenuItem(_("Help"))
		help_menu.show()
		help_menu.set_submenu(helpmenu)

		menu_bar = gtk.MenuBar()
		menu_bar.show()
		menu_bar.append (file_menu)
		menu_bar.append (category_menu)
		menu_bar.append (view_menu)
		menu_bar.append (help_menu)

		menu_bar.show()
		if IS_HILDON:
			menu = gtk.Menu()
			for child in menu_bar.get_children():
				child.reparent(menu)
			self.window.set_menu(menu)
			menu_bar.destroy()
		else:
			vbox.pack_start(menu_bar, False, False, 0)

		#Create GUI elements
		self.topBox = libkopfzeile.Kopfzeile(self.db)
		vbox.pack_start(self.topBox, False, False, 0)

		self.notizen = libnotizen.Notizen(self.db, self.topBox)
		vbox.pack_start(self.notizen, True, True, 0)

		self.window.add(vbox)
		self.window.show_all()
		self.toggle_word_wrap()

	def set_db_file(self, widget = None, data = None):
		dlg = hildon.FileChooserDialog(parent=self.window, action=gtk.FILE_CHOOSER_ACTION_SAVE)

		if self.db.ladeDirekt('datenbank'):
			dlg.set_filename(self.db.ladeDirekt('datenbank'))

		dlg.set_title(_("Choose database file"))
		if dlg.run() == gtk.RESPONSE_OK:
			fileName = dlg.get_filename()
			self.db.speichereDirekt('datenbank', fileName)

			self.db.openDB()
			self.topBox.loadCategories()
			self.notizen.loadNotes()
			dlg.destroy()

	def show_about(self, widget = None, data = None):
		dialog = gtk.AboutDialog()
		dialog.set_position(gtk.WIN_POS_CENTER)
		dialog.set_name(self.__pretty_app_name__)
		dialog.set_version(self.__version__)
		dialog.set_copyright("")
		dialog.set_website("http://axique.de/index.php?f=Quicknote")
		comments = _("%s is a note taking program; it is optimised for quick save and search of notes") % self.__pretty_app_name__
		dialog.set_comments(comments)
		dialog.run()
		dialog.destroy()

	def view_sql_history(self, widget = None, data = None, data2 = None):
		import libsqldialog
		sqldiag = libsqldialog.sqlDialog(self.db)
		res = sqldiag.run()
		sqldiag.hide()
		if res == 444:
			logging.info("exporting sql")

			dlg = hildon.FileChooserDialog(parent=self.window, action=gtk.FILE_CHOOSER_ACTION_SAVE)

			dlg.set_title(_("Select SQL export file"))
			if dlg.run() == gtk.RESPONSE_OK:
				fileName = dlg.get_filename()
				dlg.destroy()
				sqldiag.exportSQL(fileName)
			else:
				dlg.destroy()

		sqldiag.destroy()

	def delete_Category(self, widget = None, data = None):
		if (self.topBox.getCategory() == "%") or (self.topBox.getCategory() == "undefined"):
			mbox = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, _("This category can not be deleted"))
			response = mbox.run()
			mbox.hide()
			mbox.destroy()
			return

		mbox = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO, _("Are you sure to delete the current category?"))
		response = mbox.run()
		mbox.hide()
		mbox.destroy()
		if response == gtk.RESPONSE_YES:
			sql = "UPDATE notes SET category = ? WHERE category = ?"
			self.db.speichereSQL(sql, ("undefined", self.topBox.getCategory()))
			sql = "DELETE FROM categories WHERE liste = ?"
			self.db.speichereSQL(sql, (self.topBox.getCategory(), ))
			model = self.topBox.comboCategory.get_model()
			pos = self.topBox.comboCategory.get_active()
			if (pos>1):
				self.topBox.comboCategory.remove_text(pos)
				self.topBox.comboCategory.set_active(0)

	def move_Category(self, widget = None, data = None):
		dialog = gtk.Dialog(_("Choose category"), self.window, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

		dialog.set_position(gtk.WIN_POS_CENTER)
		comboCategory = gtk.combo_box_new_text()

		comboCategory.append_text('undefined')
		sql = "SELECT id, liste FROM categories WHERE id = 0 ORDER BY liste"
		rows = self.db.ladeSQL(sql)
		for row in rows:
			comboCategory.append_text(row[1])

		dialog.vbox.pack_start(comboCategory, True, True, 0)

		dialog.vbox.show_all()
		#dialog.set_size_request(400, 300)

		if dialog.run() == gtk.RESPONSE_ACCEPT:
			n = comboCategory.get_active()
			if (n>-1) and (self.notizen.noteid!= -1):
				model = comboCategory.get_model()
				active = comboCategory.get_active()
				if active < 0:
					return None
				cat_id = model[active][0]

				noteid, category, note = self.db.loadNote(self.notizen.noteid)
				#print noteid, category, cat_id
				self.db.saveNote(noteid, note, cat_id, pcdatum = None)
				self.topBox.comboCategoryChanged()
			else:
				mbox = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, _("No note selected."))
				response = mbox.run()
				mbox.hide()
				mbox.destroy()

		dialog.destroy()

	def sync_finished(self, data = None, data2 = None):
		self.topBox.loadCategories()
		self.notizen.loadNotes()

	def prepare_sync_dialog(self):
		self.sync_dialog = gtk.Dialog(_("Sync"), None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

		self.sync_dialog.set_position(gtk.WIN_POS_CENTER)
		sync = libsync.Sync(self.db, self.window, 50504)
		self.sync_dialog.vbox.pack_start(sync, True, True, 0)
		self.sync_dialog.set_size_request(500, 350)
		self.sync_dialog.vbox.show_all()
		sync.connect("syncFinished", self.sync_finished)

	def sync_notes(self, widget = None, data = None):
		self.sync_dialog.run()
		self.sync_dialog.hide()

	def toggle_word_wrap(self, *args):
		self._wordWrapEnabled = not self._wordWrapEnabled
		self.notizen.set_wordwrap(self._wordWrapEnabled)

	def delete_event(self, widget, event, data = None):
		return False

	def destroy(self, widget = None, data = None):
		self.db.close()
		if self._osso_c:
			self._osso_c.close()
		gtk.main_quit()

	def _on_device_state_change(self, shutdown, save_unsaved_data, memory_low, system_inactivity, message, userData):
		"""
		For system_inactivity, we have no background tasks to pause

		@note Hildon specific
		"""
		if memory_low:
			gc.collect()

		if save_unsaved_data or shutdown:
			pass

	def on_window_state_change(self, widget, event, *args):
		if event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN:
			self.window_in_fullscreen = True
		else:
			self.window_in_fullscreen = False

	def on_key_press(self, widget, event, *args):
		if event.keyval == gtk.keysyms.F6:
			# The "Full screen" hardware key has been pressed 
			if self.window_in_fullscreen:
				self.window.unfullscreen ()
			else:
				self.window.fullscreen ()
		elif event.keyval == gtk.keysyms.F7:
			# Zoom In
			self.topBox.hide()
		elif event.keyval == gtk.keysyms.F8:
			# Zoom Out
			self.topBox.show()

	def main(self):
		gtk.main()
