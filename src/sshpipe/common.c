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

#include <stdio.h>
#include <malloc.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>

#include "common.h"
#include "client.h"
#include "server.h"

int main(int argc, char **argv)
{
    char *host = "127.0.0.1";
    int port = 4551;
    if(argc > 1)
        server_pipe(host, port);
    else
        client_pipe(host, port);
    return 0;
}

void session_event(void *session, const char *tag, const char *data)
{
    if(data)
        fprintf(stderr, "! %s %s\n", tag, data);
    else
        fprintf(stderr, "! %s\n", tag);
}

void session_error(void *session, const char *tag)
{
    const char *error = ssh_get_error(session);
    fprintf(stderr, "! error %s %lu %s\n", tag, (unsigned long)strlen(error), error);
    exit(1);
}

char *pubkey_hash(ssh_string key)
{
    unsigned char *hash = NULL;
    if(ssh_hash_string_md5(key, &hash) < 0)
        return NULL;
    
    char *hashstr = ssh_get_hexa(hash, MD5_DIGEST_LEN);
    free(hash);
    return hashstr;
}

int authenticate(const char *keyhash, int partial)
{
    fprintf(stderr, "> user-auth %i %s\n", partial ? 0 : 1, keyhash);
    return 1;
}

void channel_to_file(ssh_channel chan, int fd)
{
    ssh_buffer buf = buffer_new();
    int n;
    do
    {
        n = channel_read_buffer(chan, buf, 0, 0);
        if(n > 0)
            write(fd, buffer_get(buf), n);
    } while(n > 0);
    buffer_free(buf);
}

void channel_from_file(ssh_channel chan, int fd)
{
    char buf[4096];
    int n;
    do
    {
        n = read(fd, buf, 4096);
        if(n > 0)
            channel_write(chan, buf, n);
    } while(n > 0);
    channel_send_eof(chan);
}