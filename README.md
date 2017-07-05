# pymonitor
linux system monitoring script written in python

# Errata:
### If you get this error:
```
Traceback (most recent call last):
  File "./pymon", line 50, in <module>
    temps = psutil.sensors_temperatures()
AttributeError: 'module' object has no attribute 'sensors_temperatures'
```
...it is likely that you need to upgrade your version of psutil.
Try this:
```
sudo pip install psutil --upgrade
```
