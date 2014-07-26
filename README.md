Cookie BREACH
============

1. `(echo. && echo 127.0.0.1 demo.cookiebreach.com) >> %windir%\system32\drivers\etc\hosts`
2. `sudo python proxy -p 443 -r 66.175.219.8 -P 443 -e 80`

      -p  Local HTTPS Proxy Port

      -r  Remote HTTPS IP

      -P  Remote HTTPS Port

      -e  Local Evil Port
3. Visit http://demo.cookiebreach.com in Browser.
