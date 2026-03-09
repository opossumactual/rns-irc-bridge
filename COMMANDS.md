# IRC Quick Reference

## First Things First

```
/oper op 1
/samode #notconfnet +o yournick
```

## Channel Modes

```
/mode #channel +t      topic lock (only ops change topic)
/mode #channel +n      no external messages
/mode #channel +p      private (hidden from /list)
/mode #channel +i      invite only
/mode #channel +m      moderated (only voiced/ops can talk)
/mode #channel +k pass set channel password
/mode #channel +l 20   user limit
```

## User Management

```
/samode #channel +o nick    give op
/samode #channel -o nick    remove op
/samode #channel +v nick    give voice (can talk in +m channels)
/kick nick reason           kick from channel
/mode #channel +b nick!*@*  ban a user
/kill nick reason           disconnect from server (oper)
```

## Channel Admin

```
/topic new topic text       set topic (need op or +t off)
/names                      list users in channel
/who #channel               detailed user list
/whois nick                 info about a user
```

## WeeChat Navigation

```
Alt+1-9         switch windows
PgUp/PgDn       scroll history
/close           close current buffer
/mouse enable    enable mouse
/fset            interactive settings browser
```

## Server Admin

```
/stats u         server uptime
/lusers          connected user count
/map             server map
```

## On the Droplet

```bash
systemctl status inspircd           # IRC server status
systemctl status rns-irc-server     # bridge status
systemctl restart inspircd          # restart IRC
systemctl restart rns-irc-server    # restart bridge
journalctl -u rns-irc-server -f    # live bridge logs
ss -tn state established dst 127.0.0.1:6667   # active connections
```
