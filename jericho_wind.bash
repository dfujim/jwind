#!/usr/bin/python3
# Draw jericho wind
# Derek Fujimoto
# May 2020
# instructions for adding to crontab to run every hour on ubuntu 18.04:
#   run "crontab -e"
#   add line "0 * * * * XDG_RUNTIME_DIR=/run/user/$(id -u) /full_path/jericho_wind.py"
# see also https://stackoverflow.com/questions/16519673/cron-with-notify-send

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from datetime import datetime, timezone
from itertools import cycle
import sys, webbrowser, subprocess, notify2
from requests_html import HTMLSession
from PIL import Image
import requests

plt.ioff()

# settings
threshold = {'Wind Speed':15,
             'Hi Speed':20}
style = {'marker':'.','ls':'-'}

# read data
df = pd.read_csv("https://jsca.bc.ca/main/downld02.txt")
columns = ["Date", "Time", "Temp Out", "Hi Temp", "Low Temp", "Out Hum", "Dew Pt.",
           "Wind Speed", "Wind Dir", "Wind Run", "Hi Speed", "Hi Dir", "Wind Chill", "Heat Index", "THW Index",
           "Bar", "Rain", "Rain Rate", "Head D-D", "Cool D-D", "In Temp", "In Hum",
           "In Dew", "In Heat", "In EMC", "In Air Density", "Wind Samp", "Wind Tx",
           "ISS Recept", "Arc Int.", ]

# get proper data frame
df = df.apply(lambda x : str.split(x[0]), axis='columns')
for i in [0,1]:
    df.drop(i,inplace=True)
data = np.vstack(df.values)

data = {k:d for k,d in zip(columns,data.T)}
df = pd.DataFrame(data)

# convert to numeric
for c in df.columns:
    try:
        df[c] = df[c].apply(pd.to_numeric)
    except ValueError:
        pass

# get proper date and time
date = df[['Date','Time']].apply(lambda x : ' '.join(x),axis=1)
date = date.apply(pd.to_datetime)

df.drop('Date', inplace=True, axis='columns')
df.drop('Time', inplace=True, axis='columns')
df.index = date

# matplotlib settings
hours = mdates.HourLocator(interval=2)
days = mdates.DayLocator()
hours_fmt = mdates.DateFormatter('%H')
days_fmt = mdates.DateFormatter('%a')

dirs = np.array(['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'])

# get url for sunrise and set
year = datetime.today().year
month = datetime.today().month
url = 'https://sunrise-sunset.org/ca/vancouver/%d/%d' % (year, month)

# get web table
session = HTMLSession()
r = session.get(url)
table = r.html.find('table', first=True)
df_sun = pd.read_html(table.html)[0]

# get timestamps for set and rise
day = df_sun['Day','Day'].apply(lambda x: ' '.join(x.split()[-2:]))
sunrise = str(year) + ' ' + day + ' ' + df_sun['Sunrise','Sunrise']   
sunset = str(year) + ' ' + day + ' ' + df_sun['Sunset','Sunset']

sunrise = pd.to_datetime(sunrise, utc=True)
sunset = pd.to_datetime(sunset, utc=True)

# wind meter image
img_url = 'https://jsca.bc.ca/main/%s.gif?0.9089939407848988'

# direction to number
class direction(object):
    dirs = cycle(dirs)

    def __init__(self):
        self.value = 0

    def get_dir(self,direction):

        if direction == '---':
            return np.nan

        for i,d in enumerate(self.dirs):

            if d == direction:
                break
            if i > 16:
                raise RuntimeError(direction)

        if self.value > 0:
            i += 1

        self.value = (self.value+i) % 16
        return self.value

dircycler = direction()

# drawing functions
def format_ax(ax, unit, is_wind=False):
    ax.xaxis.set_major_locator(days)
    ax.xaxis.set_major_formatter(days_fmt)

    ax.xaxis.set_minor_locator(hours)
    ax.xaxis.set_minor_formatter(hours_fmt)

    ax.tick_params(axis='x', which='major', labelsize=14, pad=17)
    ax.tick_params(axis='x', which='minor', labelsize=12, colors='grey')

    ax.grid(axis='y',which='major')

    ax.annot = ax.annotate("",
                     xy=(0, 0),
                     xytext=(50, 20),
                     textcoords='offset points',
                     ha='right',
                     va='bottom',
                     bbox=dict(boxstyle='round,pad=0.1',
                               fc='grey',
                               alpha=0.1),
                     arrowprops=dict(arrowstyle='->',
                                     connectionstyle='arc3,rad=0'),
                     fontsize='xx-small')
    ax.annot.set_visible(False)

    plt.gcf().canvas.mpl_connect("motion_notify_event", lambda x : hover(x,ax,unit,is_wind))

def draw_wind(ax):
    line = ax.plot(df.index,df['Wind Speed'],**style)[0]
    ax.plot(df.index,df['Hi Speed'],**style,color=line.get_color(),alpha=0.5)
    ax.set_ylabel('Wind Speed (kts)')
    format_ax(ax, 'kts')
    ax.fill_between(df.index,df['Wind Speed'],df['Hi Speed'],color=line.get_color(),alpha=0.2)

def draw_temp(ax):
    line = ax.plot(df.index,df['Temp Out'],**style)[0]
    ax.fill_between(df.index,df['Hi Temp'],df['Low Temp'],color=line.get_color(),alpha=0.2)
    ax.set_ylabel('Temperature (C)')
    format_ax(ax, "C")

def draw_direction(ax):
    y = df['Wind Dir'].apply(dircycler.get_dir)
    yhi = df['Hi Dir'].apply(dircycler.get_dir)
    line = ax.plot(df.index,y,**style)[0]
    ax.set_ylabel('Wind Direction')
    ax.set_yticks(np.arange(0,len(dirs),2))
    ax.set_yticklabels(dirs[::2])
    format_ax(ax, "", True)
    ax.fill_between(df.index,y,yhi,color=line.get_color(),alpha=0.2)

def draw_pressure(ax):
    line = ax.plot(df.index,df['Bar'],**style)[0]
    ax.set_ylabel('Pressure (Bar)')
    format_ax(ax, "Bar")

def draw_rain(ax):
    line = ax.plot(df.index,df['Rain'],**style)[0]
    ax.set_ylabel('Rain (mm)')
    format_ax(ax, "mm")

def draw_daylight(ax):
    """Draw sunrise and sunset"""
    
    # get y lim and x lim
    ylim = ax.get_ylim()
    xlim_orig = ax.get_xlim()
    xlim = list(ax.get_xlim())
    
    # get xlim as datetime
    xlim[0] = mdates.num2date(xlim[0])
    xlim[1] = mdates.num2date(xlim[1])
    
    # get drawing ranges
    sr = []
    ss = []
    
    for r,s in zip(sunrise, sunset):
        
        # out of range conditions
        if r < xlim[0] and s < xlim[0]:
            continue
        elif r > xlim[1] and s > xlim[1]:
            continue
        
        # in range
        else:
            r = r if r > xlim[0] else xlim[0]
            s = s if s < xlim[1] else xlim[1]
            
            sr.append(r)
            ss.append(s)

    # draw dark for night
    ss.insert(0, xlim[0])
    sr.append(xlim[1])
    for r, s in zip(sr,ss):
        ax.fill_between([s,r], [ylim[0], ylim[0]], [ylim[1], ylim[1]], color='k',
                        alpha=0.2)    

    # set y lim
    ax.set_ylim(ylim)
    ax.set_xlim(xlim_orig)

def draw_wind_speed_img(ax, mode='WindSpeed'):
    """
        Draw the reading spedometer
    """
    response = requests.get(img_url % mode, stream=True)
    img = Image.open(response.raw)
    ax.imshow(img)
    
    # clear axes
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    
def annotate(ind, line, ax, unit, is_wind):
    """ Show annotation """
    x,y = line.get_data()

    y_label = y
    if is_wind:
        y_label = [dirs[int(i)] if not np.isnan(i) else i for i in y]

    idx = ind["ind"][0]
    ax.annot.xy = (x[idx], y[idx])

    time = pd.to_datetime(str(x[idx])).strftime("%H:%M")

    # format time
    if type(y_label[idx]) is float:
        y = '%.1f' % y_label[idx]
    elif type(y_label[idx]) is int:
        y = '%d' % y_label[idx]
    else:
        y = str(y_label[idx])

    ax.annot.set_text('%s %s (%s)' % (y,unit,time))
    ax.annot.get_bbox_patch().set_alpha(0.1)

def hover(event,ax,unit,is_wind):
    vis = ax.annot.get_visible()
    if event.inaxes == ax:
        for line in ax.lines:
            cont, ind = line.contains(event)
            if cont:
                annotate(ind, line, ax, unit, is_wind)
                ax.annot.set_visible(True)
                plt.gcf().canvas.draw_idle()
                break
            else:
                if vis:
                    ax.annot.set_visible(False)
                    plt.gcf().canvas.draw_idle()

def do_cam():
    webbrowser.open('https://jsca.bc.ca/services/streamcam-ptz/')

def do_plot():
    fig,ax = plt.subplots(nrows=2,ncols=2,sharex=True)
    tl = plt.suptitle("Jericho Wind")
    draw_wind(ax[0,0])
    draw_temp(ax[1,0])
    draw_direction(ax[1,1])
    # ~ draw_pressure(ax[1,1])
    
    for a1 in (0, 1):
        for a2 in (0, 1):
            if a1 == 0 and a2 == 1: continue
            draw_daylight(ax[a1,a2])
    
    mng = plt.get_current_fig_manager()
    mng.resize(*mng.window.maxsize())
    plt.gcf().canvas.draw_idle()
    plt.subplots_adjust(left=0.05, bottom=0.07, right=0.97, top=0.94, wspace=0.2, hspace=0)
    
    # draw images
    inset_ax = inset_axes(ax[0, 1],
                          height="47%", # set height
                          width="47%", # and width
                          loc='center left')
    draw_wind_speed_img(inset_ax, 'WindSpeed')
    
    inset_ax = inset_axes(ax[0, 1],
                          height="47%", # set height
                          width="47%", # and width
                          loc='center')
    draw_wind_speed_img(inset_ax, 'WindDirection')
    
    inset_ax = inset_axes(ax[0, 1],
                          height="47%", # set height
                          width="47%", # and width
                          loc='center right')
    draw_wind_speed_img(inset_ax, '10MinAvgWindSpeed')
    
    ax[0, 1].set_yticks([])
    ax[0, 1].set_yticklabels([])
    
    plt.show(block=True)
    
def do_call(notif,key,data):
    if key == "plot":
        do_plot()
    elif key == "cam":
        do_cam()
    else:
        do_plot()

# draw all
if __name__ == "__main__":

    # get latest wind mode and push if above threshold
    if len(sys.argv) == 1:
        last = df[['Wind Speed','Hi Speed']].iloc[-1]
        wdir = df['Wind Dir'].iloc[-1]
        threshold = pd.Series(threshold)

        # if True:
        if any(last>threshold):
            # subprocess.call(['notify-send -t 3000 -i ~/Documents/Other/Windsurf/wind3.png "Jericho is windy!" "%.1f g %.1f kts"' % (last['Wind Speed'],last['Hi Speed'])], shell=True)
            notify2.init("jericho_wind",mainloop='glib')
            n = notify2.Notification(summary = "Jericho is windy! \t(%dg%d %s)" \
                                                % (int(np.round(last['Wind Speed'])),
                                                   int(np.round(last['Hi Speed'])),
                                                   wdir),
                                     message = "",
                                     icon = "/home/fuji/Documents/Other/Windsurf/wind3.png")
            n.set_timeout(5000)
            # n.add_action("plot","Plots",'/home/fuji/Documents/Other/Windsurf/jericho_wind.py d')
            # n.add_action("cam","Webcam",do_call)
            n.show()

    # draw mode
    elif sys.argv[1].replace('-','') in ['d','draw']:
        do_plot()

    # launch webcam
    elif sys.argv[1].replace('-','') in ['w','webcam','cam']:
        do_cam()

    else:
        print('Usage: wind [--draw] [--webcam]\nIf no option, check thresholds and push notification')
