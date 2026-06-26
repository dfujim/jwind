#!/usr/bin/python3
# Get by the minute jericho weather readings
# Derek Fujimoto
# June 2021

import os
import pandas as pd
import numpy as np
from PIL import Image
import requests
from datetime import datetime
import yaml
import matplotlib.pyplot as plt
import argparse
from pathlib import Path

# settings
img_url = 'https://jsca.bc.ca/main/%s.gif?0.9089939407848988'
data_dir = Path(__file__).parent
filename = str(data_dir / 'wind_data.csv')

# get data
try:
    df = pd.read_csv(filename)
except FileNotFoundError:
    df = pd.DataFrame(columns=['Date', 'Speed (kts)', 'Direction (deg)'])

def get_direction(draw=False):

    # get image
    response = requests.get(img_url % 'WindDirection', stream=True)
    img = Image.open(response.raw)
    dat = np.array(img)

    # get origin
    x0 = 96
    y0 = 93

    # isolate marker
    dat[dat != 3] = 0
    dat[dat == 3] = 1

    # get point furthest from origin
    rmax = 0
    for i in range(dat.shape[0]):
        for j in range(dat.shape[1]):
            if dat[i,j]:
                r2 = (x0-j)**2 + (y0-i)**2
                if r2 > rmax:
                    rmax = r2
                    xmax = j
                    ymax = i

    # get angle from N
    dx = xmax-x0
    dy = y0-ymax

    angle = np.arctan(abs(dx/dy))*180/np.pi # degrees

    if dx > 0 and dy < 0: angle += 90
    if dx < 0 and dy < 0: angle += 180
    if dx < 0 and dy > 0: angle += 270

    # draw
    if draw:
        plt.imshow(img)
        plt.figure()
        plt.imshow(dat)
        plt.axhline(y0)
        plt.axvline(x0)
        plt.axhline(ymax)
        plt.axvline(xmax)

    return angle

def get_wind(draw=False):

    # get image
    response = requests.get(img_url % 'WindSpeed', stream=True)
    img = Image.open(response.raw)
    dat = np.array(img)

    # get number definitions
    with open(data_dir / 'numbers.yaml', 'r') as fid:
        numbers = yaml.safe_load(fid)

    # get rows for windspeed
    idx_top = 136
    idx_bot = 146
    wind = dat[idx_top:idx_bot, :]

    # trim column edges
    wind = wind[:, 5:-5]

    # get columns corresponding to each character
    xproj = np.sum(wind, axis=0).astype(bool)

    char_ranges = []
    in_character = False
    clow = 0
    chi = 0
    for i, x in enumerate(xproj):

        if in_character:
            if not x:
                chi = i
                char_ranges.append([clow, chi])
                in_character = False
        else:
            if x:
                clow = i
                in_character = True

    # id the numbers
    number_string = []
    for i in range(len(char_ranges)):
        for k, n in numbers.items():
            try:
                if np.equal(n, wind[:,char_ranges[i][0]:char_ranges[i][1]]).all():
                    number_string.append(k)
            except ValueError:
                continue

    number_string = ''.join(number_string)

    if draw:
        plt.figure()
        plt.imshow(wind)
        plt.title(number_string)

    return float(number_string) if number_string else float('nan')

def draw(col='Speed (kts)', window=5, ax=None, hours_shown=6):
    """
        col: 'Speed (kts)' or 'Direction (deg)'
        Window: rolling window size in min
        ax: plt.ax drawing axis
        hours_shown: time drawn in h
    """

    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    if ax is None:
        plt.figure()
        ax = plt.gca()

    # read data
    df = pd.read_csv(filename)
    df['Date'] = pd.to_datetime(df['Date'])

    # take average
    rolling = df[col].rolling(window, center=True)
    df['avg'] = rolling.mean()

    # get last datetime
    last_time = df['Date'].max()

    # convert to hours before last reading
    df['Date'] = (df['Date'] - df['Date'].max()).dt.total_seconds() / 3600

    # crop to duration
    idx = df['Date'].abs() < hours_shown
    df = df.loc[idx]

    # draw
    ax.plot(df['Date'], df['avg'])

    # plot elements
    ax.grid(axis='y',which='major')

    last_time_str = last_time.strftime('%Y-%m-%d %H:%M')
    ax.set_xlabel(f'Time Since {last_time_str} (hours)')
    ax.set_xlim(None, 0)

    if col == 'Direction (deg)':

        ylim = ax.get_ylim()

        ax.set_yticks([ 0,  22.5,  45,  67.5,  90, 112.5, 135, 157.5, 180,
                        202.5, 225, 247.5, 270, 292.5, 315, 337.5])
        ax.set_yticklabels(['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                            'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'])
        ax.set_ylim(ylim)
    else:
        ax.set_ylabel('Wind Speed (kts)')

    if len(ax.figure.axes) == 1:
        ax.figure.tight_layout()

def draw_pretty(window=5, hours_shown=6):
    """Draw pretty two axis figure"""

    _, (ax1, ax2) = plt.subplots(nrows=2,
                                   ncols=1,
                                   sharex=True,
                                   sharey=False,
                                   layout='constrained',
                                   figsize=(7, 7),
                                   gridspec_kw = {'hspace':0.025}
                                   )

    draw('Direction (deg)', window, ax1, hours_shown)
    draw('Speed (kts)', window, ax2, hours_shown)

    ax1.set_xlabel('')
    ax1.set_ylabel('Wind Direction')
    plt.show(block=True)

if __name__ == '__main__':

    # setup input arguments
    parser = argparse.ArgumentParser(add_help=True)

    parser.add_argument('-w', '--window', type=int, default=5,
                        help='Duration of averaging window for rolling average in minutes')

    parser.add_argument('-t', '--time', type=float, default=6,
                        help='Duration of data shown in hours')

    parser.add_argument('-d', '--draw', action='store_true',
                        help='Draw the wind')

    args, remaining = parser.parse_known_args()

    # get data
    if not args.draw:

        # get wind and time
        wind = get_wind()
        direction = get_direction()
        date = str(datetime.now())

        # add to data frame
        df = pd.concat((df, pd.DataFrame({'Date':[date], 'Speed (kts)':[wind], 'Direction (deg)':[direction]})),
                    ignore_index=True)

        # Trim oldest rows to stay under 1 GB; estimate row budget from current file size
        max_bytes = 1 * 1024**3
        if os.path.exists(filename) and len(df) > 1:
            bytes_per_row = os.path.getsize(filename) / len(df)
            max_rows = int(max_bytes / bytes_per_row)
            if len(df) > max_rows:
                df = df.iloc[-max_rows:]

        # write to file
        df.to_csv(filename, index=False)

    # draw
    else:
        draw_pretty(window=args.window, hours_shown=args.time)