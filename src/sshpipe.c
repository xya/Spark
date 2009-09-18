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

#include <libssh/libssh.h>
#include <libssh/server.h>

int main(int argc, char **argv)
{
    char *host = "127.0.0.1";
    int port = 4551;
    return client_pipe(host, port);
}

// Connect to a SSH server.
// When the connection is established, read data from stdin and send it to the server.
int client_pipe(char *host, int port)
{
    SSH_OPTIONS *opt = ssh_options_new();
    ssh_options_set_host(opt, host); 
    ssh_options_set_port(opt, port);
    
    SSH_SESSION *s = ssh_connect(opt);
    if(!s)
    {
        fprintf(STDERR, "error connect %s\n", ssh_get_error(s));
        return 1;
    }
    else
    {
        fprintf(STDERR, "connected\n");
    }
    
    char hash[MD5_DIGEST_LEN];
    ssh_get_pubkey_hash(s, hash);
    fprintf(STDERR, "public-key %s\n", hash);
    
    int keytype;
    ssh_string pub = publickey_from_file(s, "test-client-key.pub", &keytype);
    if(SSH_AUTH_SUCCESS != ssh_userauth_offer_pubkey(s, "sshpipe", keytype, pub))
    {
        fprintf(STDERR, "error offer-public-key %s\n", ssh_get_error(s));
        return 1;
    }
    
    ssh_private_key priv = privatekey_from_file(s, "test-client-key.priv", keytype, NULL);
    if(!priv)
    {
        fprintf(STDERR, "error open-private-key %s\n", ssh_get_error(s));
        return 1;
    }
    if(SSH_AUTH_SUCCESS != ssh_userauth_pubkey(s, "sshpipe", pub, priv))
    {
        fprintf(STDERR, "error offer-public-key %s\n", ssh_get_error(s));
        return 1;
    }
    string_free(pub);
    private_key_free(priv);
    
    ssh_channel chan = channel_new(s);
    if(!chan)
    {
        fprintf(STDERR, "error create-channel %s\n", ssh_get_error(s));
        return 1;
    }
    else if(SSH_SUCCESS != channel_open_session(chan))
    {
        fprintf(STDERR, "error open-channel %s\n", ssh_get_error(s));
        return 1;
    }
    else
    {
        fprintf(STDERR, "channel-opened\n");
    }
    char buf[4096];
    int read;
    do
    {
        read = read(STDIN, buf, 4096);
        if(read > 0)
            channel_write(chan, buf, read);
    } while (read > 0);
    channel_send_eof(chan);
    channel_free(chan);
    ssh_disconnect(s);
    ssh_finalize();
    return 0;
}

#define SERVER_CLOSED           0
#define SERVER_CONNECTED        1
#define SERVER_AUTHENTICATED    2
#define SERVER_CHANNEL_OPENED   3

// Listen for incoming SSH connections.
// When a connection is established, write all data received to stdout.
int server_pipe(char *host, int port)
{
    SSH_OPTIONS *opt = ssh_options_new();
    ssh_options_set_dsa_server_key(opt, "test-server-key");
    ssh_options_set_auth_methods(opt, SSH_AUTH_METHOD_PUBLICKEY);
    
    SSH_BIND *b = ssh_bind_new();
    ssh_bind_set_options(b, opt);
    if(ssh_bind_listen(b) < 0)
    {
        fprintf(STDERR, "error listen %s\n", ssh_get_error(b));
        return 1;
    }
    
    SSH_SESSION *s = ssh_bind_accept(b);
    if(!s)
    {
        fprintf(STDERR, "error accept %s\n", ssh_get_error(b));
        return 1;
    }
    fprintf(STDERR, "connected\n");
    
    int state = SERVER_CONNECTED;
    while(1)
    {
        SSH_MESSAGE *m = ssh_message_get(s);
        if(m)
        {
            int type = ssh_message_type(m);
            int subtype = ssh_message_subtype(m);
            ssh_message_auth_set_methods(m, SSH_AUTH_METHOD_PUBLICKEY);
            server_handle_message(m, type, subtype, &state);
            ssh_message_free(m);
            if(state == SERVER_CLOSED)
            {
                ssh_disconnect(s);
                ssh_bind_free(b);
                ssh_finalize();
                return 0;
            }
        }
        else
        {
            fprintf(STDERR, "error session %s\n", ssh_get_error(s));
            return 1;
        }
    }
}

void server_handle_message(SSH_MESSAGE *m, int type, int subtype, int *state)
{
    if((*state == SERVER_CONNECTED) && (type == SSH_REQUEST_AUTH) && (subtype == SSH_AUTH_METHOD_PUBLICKEY))
    {
        ssh_public_key key = ssh_message_auth_publickey(m);
        ssh_string keystr = publickey_to_string(key);
        ssh_string algostr = string_from_char(ssh_type_to_char(key->type));
        fprintf(STDERR, "public-key\n");
        ssh_message_auth_reply_pk_ok(m, 0, keystr);
        string_free(keystr);
        *state = SERVER_AUTHENTICATED;
        return;
    }
    else if((*state == SERVER_AUTHENTICATED) && (type == SSH_REQUEST_CHANNEL_OPEN) && (subtype == SSH_CHANNEL_SESSION))
    {
        fprintf(STDERR, "channel-opened\n");
        ssh_channel chan = ssh_message_channel_request_open_reply_accept(m);
        if(chan)
        {
            ssh_buffer buf = buffer_new();
            int read;
            do
            {
                read = channel_read_buffer(chan, buf, 0, 0);
                if(read > 0)
                    write(STDOUT, buffer_get(buf), buffer_get_len(buf));
            } while (read > 0);
            buffer_free(buf);
        }
        *state = SERVER_CLOSED;
        return;
    }
    ssh_message_reply_default(m);
}