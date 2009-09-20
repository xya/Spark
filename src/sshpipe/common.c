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

#include "common.h"
#include "client.h"
#include "server.h"

int main(int argc, char **argv)
{
    char *host = "127.0.0.1";
    int port = 4551;
    if(argc > 1)
        return server_pipe(host, port);
    else
        return client_pipe(host, port);
}

int session_error(void *session, const char *tag)
{
    const char *error = ssh_get_error(session);
    fprintf(stderr, "error %s %lu %s\n", tag, (unsigned long)strlen(error), error);
    return 1;
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