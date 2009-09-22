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

#ifndef SSHPIPE_COMMON_H
#define SSHPIPE_COMMON_H

#include <libssh/libssh.h>

char *pubkey_hash(ssh_string key);
int authenticate(const char *keyhash, int partial);
void session_event(void *session, const char *tag, const char *data);
void session_error(void *session, const char *tag);
void channel_to_file(ssh_channel chan, int fd);
void channel_from_file(ssh_channel chan, int fd);

#endif