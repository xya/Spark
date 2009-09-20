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
#include <unistd.h>

#include "common.h"
#include "client.h"

// Connect to a SSH server.
// When the connection is established, read data from stdin and send it to the server.
int client_pipe(char *host, int port)
{
    SSH_OPTIONS *opt = ssh_options_new();
    ssh_options_set_host(opt, host);
    ssh_options_set_port(opt, port);
    ssh_options_set_username(opt, "xya");
    
    SSH_SESSION *s = ssh_new();
    ssh_set_options(s, opt);
    if(ssh_connect(s) < 0)
        return session_error(s, "connect");
    
    char *hash = pubkey_hash(ssh_get_pubkey(s));
    if(authenticate(hash, 0))
    {
        fprintf(stderr, "! authenticated %s\n", hash);
        free(hash);
    }
    else
    {
        free(hash);
        return 1;
    }
    
    int keytype;
    ssh_string pub = publickey_from_file(s, "test-client-key.pub", &keytype);
    if(!pub)
        return session_error(s, "open-public-key");
    if(SSH_AUTH_SUCCESS != ssh_userauth_offer_pubkey(s, NULL, keytype, pub))
        return session_error(s, "offer-public-key");
    
    ssh_private_key priv = privatekey_from_file(s, "test-client-key", keytype, NULL);
    if(!priv)
        return session_error(s, "open-private-key");
    if(SSH_AUTH_SUCCESS != ssh_userauth_pubkey(s, NULL, pub, priv))
        return session_error(s, "user-auth");
    string_free(pub);
    privatekey_free(priv);
    
    ssh_channel chan = channel_new(s);
    if(!chan)
        return session_error(s, "create-channel");
    if(channel_open_session(chan) < 0)
        return session_error(s, "open-channel");
    fprintf(stderr, "! channel-opened\n");
    
    char buf[4096];
    int n;
    do
    {
        n = read(0, buf, 4096);
        if(n > 0)
            channel_write(chan, buf, n);
    } while (read > 0);
    channel_send_eof(chan);
    channel_free(chan);
    ssh_disconnect(s);
    ssh_finalize();
    return 0;
}