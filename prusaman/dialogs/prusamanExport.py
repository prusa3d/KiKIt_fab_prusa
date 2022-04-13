# -*- coding: utf-8 -*-

###########################################################################
## Python code generated with wxFormBuilder (version 3.10.1-0-g8feb16b)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc

###########################################################################
## Class PrusamanExportBase
###########################################################################

class PrusamanExportBase ( wx.Dialog ):

	def __init__( self, parent ):
		wx.Dialog.__init__ ( self, parent, id = wx.ID_ANY, title = wx.EmptyString, pos = wx.DefaultPosition, size = wx.Size( 1000,700 ), style = wx.CAPTION|wx.CLOSE_BOX|wx.DEFAULT_DIALOG_STYLE|wx.DIALOG_NO_PARENT|wx.MAXIMIZE_BOX|wx.MINIMIZE_BOX|wx.RESIZE_BORDER )

		self.SetSizeHints( wx.DefaultSize, wx.DefaultSize )

		topLevelSizer = wx.BoxSizer( wx.VERTICAL )

		gridSizer = wx.FlexGridSizer( 0, 2, 0, 0 )
		gridSizer.AddGrowableCol( 1 )
		gridSizer.SetFlexibleDirection( wx.BOTH )
		gridSizer.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		self.outDirLabel = wx.StaticText( self, wx.ID_ANY, u"Output directory:", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
		self.outDirLabel.Wrap( -1 )

		gridSizer.Add( self.outDirLabel, 0, wx.ALL|wx.EXPAND, 10 )

		self.outDirSelector = wx.DirPickerCtrl( self, wx.ID_ANY, wx.EmptyString, u"Select output directory", wx.DefaultPosition, wx.DefaultSize, wx.DIRP_SMALL|wx.DIRP_USE_TEXTCTRL )
		gridSizer.Add( self.outDirSelector, 0, wx.ALL|wx.EXPAND, 5 )

		self.configurationLabel = wx.StaticText( self, wx.ID_ANY, u"Output configuration:", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
		self.configurationLabel.Wrap( -1 )

		gridSizer.Add( self.configurationLabel, 0, wx.ALL|wx.EXPAND, 10 )

		self.configurationInput = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
		gridSizer.Add( self.configurationInput, 0, wx.ALL|wx.EXPAND, 5 )


		gridSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.werrorCheckbox = wx.CheckBox( self, wx.ID_ANY, u"Treat warnings as errors", wx.DefaultPosition, wx.DefaultSize, 0 )
		gridSizer.Add( self.werrorCheckbox, 0, wx.ALL|wx.EXPAND, 5 )


		topLevelSizer.Add( gridSizer, 0, wx.EXPAND, 5 )

		buttonSizer = wx.BoxSizer( wx.HORIZONTAL )


		buttonSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.exportButton = wx.Button( self, wx.ID_ANY, u"Export", wx.DefaultPosition, wx.DefaultSize, 0 )

		self.exportButton.SetDefault()
		buttonSizer.Add( self.exportButton, 0, wx.ALL, 5 )


		topLevelSizer.Add( buttonSizer, 0, wx.EXPAND, 5 )

		self.m_staticline1 = wx.StaticLine( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LI_HORIZONTAL )
		topLevelSizer.Add( self.m_staticline1, 0, wx.EXPAND |wx.ALL, 5 )

		self.outputLabel = wx.StaticText( self, wx.ID_ANY, u"Export process output:", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.outputLabel.Wrap( -1 )

		topLevelSizer.Add( self.outputLabel, 0, wx.ALL|wx.EXPAND, 5 )

		self.outputProgressbar = wx.Gauge( self, wx.ID_ANY, 100, wx.DefaultPosition, wx.DefaultSize, wx.GA_HORIZONTAL )
		self.outputProgressbar.SetValue( 0 )
		topLevelSizer.Add( self.outputProgressbar, 0, wx.ALL|wx.EXPAND, 5 )

		self.outputText = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_LEFT|wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_WORDWRAP )
		self.outputText.SetFont( wx.Font( 11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, wx.EmptyString ) )

		topLevelSizer.Add( self.outputText, 1, wx.ALL|wx.EXPAND, 5 )


		self.SetSizer( topLevelSizer )
		self.Layout()

		self.Centre( wx.BOTH )

		# Connect Events
		self.exportButton.Bind( wx.EVT_BUTTON, self.onExport )

	def __del__( self ):
		pass


	# Virtual event handlers, override them in your derived class
	def onExport( self, event ):
		event.Skip()


