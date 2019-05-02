#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu May  2 11:52:34 2019

@author: maximilian
"""

import numpy as np
import time
from threading import Thread
from traits.api import HasTraits, Range, File, Float, Enum, Array, Instance, Int, String, Bool, Button, List, Tuple, Dict, Directory, HTML
from traitsui.api import spring,Handler, Tabbed, View, Item, VGroup, HGroup, CodeEditor, HTMLEditor, RangeEditor, ButtonEditor, ListStrEditor, InstanceEditor
from chaco.api import GridContainer,ArrayPlotData, ArrayDataSource, add_default_grids, PlotAxis, Legend, OverlayPlotContainer, LinearMapper, Plot, jet,LinePlot, DataRange1D
from chaco.tools.api import LineSegmentTool, PanTool, ZoomTool, BroadcasterTool, LegendTool, LegendHighlighter
from chaco.scales.api import CalendarScaleSystem, TimeScale,TimeFormatter
from chaco.scales_tick_generator import ScalesTickGenerator
from chaco.chaco_plot_editor import ChacoPlotItem
from enable.api import ComponentEditor, Component

###serial libraries
import serial

import struct

class LinePlotClass(HasTraits):
    plot = Instance(Component)
    time_ds = Instance(ArrayDataSource)
    value_ds = Instance(ArrayDataSource)
#    name = String()
    
    
    traits_view = View(VGroup(Item('plot', editor=ComponentEditor(), show_label=False),show_border=True), title="Chaco Plot")
    
    def create_container(self):
        
        container = OverlayPlotContainer(padding = 50, fill_padding = False,
                                     bgcolor = "lightgray", use_backbuffer=True)
        
        plots = {}
        broadcaster = BroadcasterTool()
        
        indexmapper = LinearMapper(range=DataRange1D(self.time_ds))

        valuemapper = LinearMapper(range=DataRange1D(self.value_ds))
                
        plot = LinePlot(index=self.time_ds, value=self.value_ds,
                    index_mapper = indexmapper,
                    value_mapper = valuemapper,
                    orientation = "h",
                    color = "red",
                    bgcolor = "white",
                    line_width = 1.0,
                    line_style = "solid",
                    border_visible=True)
            
            
        plot.index.sort_order = "ascending"
        add_default_grids(plot)
                #add_default_axes(plot)
        
    
        container.add(plot)
        plots[0] = plot
        
        plot.tools.append(PanTool(plot, drag_button='left'))
        self.zoom = ZoomTool(plot)
        plot.overlays.append(self.zoom) 
        
        y_axis = PlotAxis(plots[0], orientation="left", title="B-Field")
        plots[0].underlays.append(y_axis)
        
        t_axis = PlotAxis(plots[0], orientation="bottom",# mapper=xmapper,
                    tick_generator=ScalesTickGenerator(scale=TimeScale(seconds=10),formatter=TimeFormatter()), title="Time")
        plots[0].underlays.append(t_axis)
        
       
        
        return container
        
    
    def _plot_default(self):      
        
        self.time_ds = ArrayDataSource([])
        self.value_ds = ArrayDataSource([])
        
        return self.create_container()        
        
        
    def update_plot(self, bfielddata, timedata):
        self.time_ds.set_data(timedata)
        self.value_ds.set_data(bfielddata)

        self.plot = self.create_container()
            
class AcqThread(Thread):
     
     def run(self):
        start = time.time()  
        while not self.wants_abort:
             self.master.ser.reset_input_buffer()
             first = True
             while(first == True):
                  if self.master.ser.read() == b'l':
                       if self.master.ser.read() == b'a':
                            if self.master.ser.read() == b'v':
                                 threebytes = self.master.ser.read(3)
                                 first = False
             #convert 3 bytes to int  
             val = struct.unpack('<i',threebytes+b'\x00')[0]
             self.master.data.xdata.append(val)
             self.master.data.index.append(time.time()-start)
             print('got data')
             time.sleep(1./self.master.sampling_rate)
          
             
     
class Data(HasTraits):
     xdata = List()
     xval = Float()
     index = List()
     xplot=Instance(LinePlotClass)
#     ydata = List()
#     zdata = List()
     
     master = None
     
     traits_view = View(HGroup(Item('xplot', editor=InstanceEditor(),style='custom',label="X:"),
                               Item('xval',style='readonly',label='X ')))
     
#     def __init__(self):
#          self.xplot = LinePlotClass()
     
     
     def _index_items_changed(self):
          print('updated data')
          bfielddata = np.array(self.xdata)*self.master.gauss_per_level - self.master.offset
          self.xval = bfielddata[-1]
          self.xplot.update_plot(bfielddata, np.array(self.index))
     
class controller(HasTraits):
     address = String('/dev/ttyUSB1')
     baudrate = Int(128000)
     connect = Button()
     connected = Bool(False)
     
     gauss_per_level = Float(1)
     offset = Float(0)
     set_Btn = Button("Set Pulse")
     reset_Btn = Button("Reset Pulse")
     start_stop = Button('Start/Stop')
     running = Bool(False)
     sampling_rate = Float(1)
     #DATA Container
     data = Instance(Data)
     acquisition_thread = Instance(AcqThread)
     
     ser = None
     
     traits_view = View(HGroup(
                              VGroup(
                                        HGroup('address','baudrate', Item('connect',show_label=False),Item('connected',style='readonly')),
                                        HGroup(
                                                  VGroup(Item('data',editor=InstanceEditor(),style='custom',show_label=False)),
                                                  VGroup('gauss_per_level', 'offset',Item('sampling_rate',editor=RangeEditor(low=1,high=50,mode='slider')),Item('set_Btn',show_label=False),Item('reset_Btn',show_label=False))
                                             )),
                              VGroup(Item('start_stop',show_label=False))
                              )
                       )
     
     def __init__(self):
          self.data = Data()
          self.data.master = self
          self.data.xplot = LinePlotClass()
     
     
     def _connect_fired(self):
          try:
               self.ser = serial.Serial(self.address,baudrate=self.baudrate)
               self.connected = True
          except:
               print('connecting failed...')
               self.connected = False
               
     def _start_stop_fired(self):
          ##start thread
          if self.connected == True:
               if self.acquisition_thread and self.acquisition_thread.isAlive():
                 print "Stopped measuring!"
                 self.acquisition_thread.wants_abort=True
                 self.acquisition_thread = None
               else:
                 print "Started measuring!"
                 #delete old data
                 self.data.xdata = []
                 self.data.index = []
                 
                 #start thread
                 self.acquisition_thread=AcqThread()
                 self.acquisition_thread.wants_abort=False
                 self.acquisition_thread.master=self
                 
                 self.acquisition_thread.start()
          else:
               print('not connected')
          
          
          
     def _set_Btn_fired(self):
          self.ser.write(b's')
          
     def _reset_Btn_fired(self):
          self.ser.write(b'r')
          
          
if __name__== '__main__':
    s=controller()
    s.configure_traits()