#!/usr/bin/env python3

import argparse
import pprint
import csv
import os
import json
import shutil
import datetime
from typing import List, Dict, Any, Union
from termcolor import cprint
from pathlib import Path

COLORS = {'INFO': "grey", 'WARNING': "yellow", 'ERROR': "red", 'DEBUG': "cyan", 'GOOD': "green"}

def filter_logfile(logfile: str) -> Dict[str, str]:
    """
    Parses the log file and returns a dict of {category: [ lines]}
    """
    # print(f"INFO::: __filter_logfile__(logfile={logfile}")
    report_lines = {}
    if os.path.exists(logfile):
        with open(logfile, 'r') as lf:
            for line in lf:
                cat = line.split()[3]
                if cat not in report_lines.keys():
                    report_lines[cat] = []
                report_lines[cat].append(line.rstrip())
    else:
        raise FileNotFoundError(f"Specified file was not found ({logfile})")
    return report_lines

def zip_files(dir_path: str, quiet: bool =False) -> None:
    """
    Zips up the files in the specified directory for shipping 
    """
    # print(f"INFO::: __zip_files__(dir_path={dir_path}, quiet={quiet})")
    zipfile = 'csvs'
    shutil.make_archive(zipfile, 'zip', dir_path)
    if not quiet:
        print(f"Created {zipfile}.zip from directory {dir_path}")

def write_csvs(csv_lines: Dict[str, Union[str, Dict[str, str]]], quiet: bool =False) -> None:
    """
    Writes the data collected from the logfile to CSVs
    """
    # print(f"INFO::: __write_csvs__(csv_lines={csv_lines}, quiet={quiet}")
    dir_path = 'csvs'
    os.makedirs(dir_path, exist_ok=True)
    file_write_time = int(round(datetime.datetime.now(datetime.timezone.utc).timestamp()))
    # print(f"INFO::: File write time: {file_write_time}")
    fieldnames = {
        'cpu': ['Timestamp', 'Percent', 'Logical CPUs', 'Physical CPUs'],
        'memory': ['Timestamp', 'Total (B)', 'Free (B)', 'Percent', 'Used (B)'],
        'swap': ['Timestamp', 'Total', 'Free', 'Percent', 'Used'],
        'disk': ['Timestamp', 'Path', 'Total', 'Free', 'Percent'],
        'net_if': ['Timestamp', 'Interface Name', 'IsUp', 'MTU', 'Speed Mbps', 'IPs'],
        'net_errors': ['Timestamp', 'Interface Name', 'Errors In', 'Errors Out', 'Dropped In', 'Dropped Out']
    }
    if not quiet:
        print(f"{dir_path} ensured to exist.")
    for cat in csv_lines.keys():
        fn = f"{dir_path}/{cat}_{file_write_time}.csv"
        print(f"INFO::: csv_lines[{cat}] is of type {str(type(csv_lines[cat]))}")
        with open(fn, 'w') as csvout:
            spamwriter = csv.DictWriter(csvout, fieldnames=fieldnames[cat])
            spamwriter.writeheader()
            for line in csv_lines[cat]:
                # print(f"INFO::: line is type {str(type(line))}")
                spamwriter.writerow(line)
        if not quiet:
            print(f"  [{fn}]")
    zip_files(dir_path, quiet)

DEFAULT_CATEGORIES = ['cpu', 'memory', 'swap', 'disk', 'net_if', 'net_errors']

def run_categories(categories: List[str], logfile: str, include_loopback: bool = False) -> None:
    """
    This function does the "interesting" work in terms of processing the log data and converting it to a format
    better suited for metrics (charting, etc.)
    """
    # print(f"INFO::: __run_categories__(categories={categories}, logfile={logfile}, include_loopback={include_loopback}")
    # filtered lines from the logfile parsed into categories
    # each category is the key in the dict, with the relevant lines comprising the values
    lines = filter_logfile(logfile)
    # csv_lines will hold the raw csv data to be shipped to the reporting platform.
    # cav_lines[cat, comma-separated-lines]
    csv_lines = {}
    for cat in categories:
        if cat not in csv_lines.keys():
            csv_lines[cat] = []
        for line in lines[cat]:
            parts = line.split()
            ts = "T".join([parts[0], parts[1].replace(',', '.')])
            if cat == 'cpu':
                pcnt = parts[4].split('=')[1].strip(',')
                lcpu = parts[5].split('=')[1].strip(',')
                pcpu = parts[6].split('=')[1].strip(',')
                csv_lines[cat].append([ts,pcnt,lcpu,pcpu])
            elif cat == 'memory':
                total = parts[4].split('=')[1].strip(',') 
                avail = parts[5].split('=')[1].strip(',')
                pct = parts[6].split('=')[1].strip(',')
                used = parts[7].split('=')[1].strip(',')
                csv_lines[cat].append([ts,total,avail,used,pcnt])
            elif cat == 'swap':
                total = parts[4].split('=')[1].strip(',')
                free = parts[5].split('=')[1].strip(',')
                pct = parts[6].split('=')[1].strip(',')
                used = parts[7].split('=')[1].strip(',')
                csv_lines[cat].append([ts,total,free,pct,used])
            elif cat == 'disk':
                # Sample Data
                #2025-12-16 20:22:13,509 INFO disk path=/, total=103705931776, free=83575291904, percent=15.9
                path = parts[4].split('=')[1].strip(',')
                total = parts[5].split('=')[1].strip(',')
                free = parts[6].split('=')[1].strip(',')
                pct = parts[7].split('=')[1].strip(',')
                csv_lines[cat].append([ts,path,total,free,pct])
            elif cat == 'net_if':
                for ifc in parts[4:]:
                    ifname,data = ifc.split('=')
                    #if ifname not in csv_lines[cat].keys():
                    #    csv_lines[cat][ifname] = {}
                    data = json.loads(data.rstrip(','))
                    #print(f"{ifname} == {data}")
                    csv_lines[cat].append([ts,ifname,data['isup'],data['mtu'],data['speed_mbps'],data['ips']])
            elif cat == 'net_errors':
                for ifc in parts[4:]:
                    ifname,data = ifc.split('=')
                    data = json.loads(data.rstrip(','))
                    # print(f"INFO::: {ifname} == {data}")
                    line_dict = {
                        'Timestamp': ts,
                        'Interface Name': ifname,
                        'Errors In': data['errin'],
                        'Errors Out': data['errout'],
                        'Dropped In': data['dropin'],
                        'Dropped Out': data['dropout']
                    }
                    csv_lines[cat].append(line_dict)
            else: 
                raise NotImplementedError(f"{cat} is currently unhandled.")
    #print(csv_lines)
    write_csvs(csv_lines)
            
def parse_arguments() -> argparse.Namespace:
    """
    Handle command line arguments
    """
    # print(f"INFO::: __parse_arguments__()")
    # argument parsing
    parser = argparse.ArgumentParser()
    parser.add_argument('categories', nargs="?", help="Comma separated list of categories to prep for shipping.")
    vqd = parser.add_mutually_exclusive_group()
    vqd.add_argument('-v', '--verbose', dest='verbose', action='store_true', help="Add more output.")
    vqd.add_argument('-q', '--quiet', dest='quiet', action='store_true', help='Suppress all output, except errors. AKA "Cron Mode"')
    vqd.add_argument('-d', '--debug', dest='debug', action='store_true', help='All the outputs.  For debugging.')
    parser.add_argument('-l', '--logfile', dest='logfile', required=True, help='The full path to the logfile to be parsed.')
    parser.add_argument('-n', '--no-clobber', dest='noclobber', required=False, help='Fails if attemping to overwrite files and/or delete things during cleanup.')
    parser.add_argument('--include-loopback', dest='include_loopback', action='store_true', default=False, help='Include the loopback interface in netwoirk statistics.  Default: False')
    return parser.parse_args()

def destroy_on_filesystem(to_delete: List[str]) -> None:
    """
    Delete the files and folder created.
    """
    for obj in to_delete:
        __path = Path(obj)
        if os.path.isfile(__path):
            try:
                __path.unlink()
            except FileNotFoundError:
                cprint(f"Error: {__path} not found.", "red")
            except OSError as e:
                cprint(f"Error deleting file: {e}", "red")
        elif os.path.isdir(__path):
            try:
                shutil.rmtree(__path)
            except FileNotFoundError:
                cprint(f"Error: {__path} not found.", "red")
            except OSError as e:
                cprint(f"Error deleting directory tree: {e}")
        else:
            cprint(f"Can't determine filesystem object type for (__path).", "yellow")

def main():
    #print(f"{__name__}")

    # pretty printing for objects
    pp = pprint.PrettyPrinter(indent=4)

    # argument handling
    args = parse_arguments()

    if args.categories:
        cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    else:
        cats = DEFAULT_CATEGORIES
    run_categories(cats, args.logfile, include_loopback=args.include_loopback)

    if not args.noclobber:
        destroy_on_filesystem(['./csvs/'])

if __name__=='__main__':
    main()
