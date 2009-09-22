/*
 Copyright (C) 2009 Pierre-André Saulais <pasaulais@free.fr>

 This file is part of the Spark File-transfer Tool.

 Spark is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 2 of the License, or
 (at your option) any later version.

 Spark is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with Spark; if not, write to the Free Software
 Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
*/

#ifndef SSHPIPE_SERVER_H
#define SSHPIPE_SERVER_H

#include <libssh/libssh.h>

#define SERVER_CLOSED           0
#define SERVER_CONNECTED        1
#define SERVER_AUTHENTICATED    2
#define SERVER_CHANNEL_OPENED   3

void server_pipe(char *host, int port);
void server_handle_message(SSH_SESSION *s, SSH_MESSAGE *m, int type, int subtype, int *state);
#endif