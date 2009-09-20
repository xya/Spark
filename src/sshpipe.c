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
#include <unistd.h>
#include <malloc.h>
#include <string.h>

#include <libssh/libssh.h>
#include <libssh/server.h>

int main(int argc, char **argv)
{
    char *host = "127.0.0.1";
    int port = 4551;
    if(argc > 1)
        return server_pipe(host, port);
    else
        return client_pipe(host, port);
}

char *pubkey_hash(ssh_string key);
int authenticate(const char *keyhash, int partial);

int session_error(void *session, const char *tag)
{
    const char *error = ssh_get_error(session);
    fprintf(stderr, "error %s %lu %s\n", tag, (unsigned long)strlen(error), error);
    return 1;
}

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

#define SERVER_CLOSED           0
#define SERVER_CONNECTED        1
#define SERVER_AUTHENTICATED    2
#define SERVER_CHANNEL_OPENED   3

void server_handle_message(SSH_MESSAGE *, int, int, int *);

// Listen for incoming SSH connections.
// When a connection is established, write all data received to stdout.
int server_pipe(char *host, int port)
{
    SSH_OPTIONS *opt = ssh_options_new();
    ssh_options_set_host(opt, host);
    ssh_options_set_port(opt, port);
    ssh_options_set_rsa_server_key(opt, "test-server-key");
    
    SSH_BIND *b = ssh_bind_new();
    ssh_bind_set_options(b, opt);
    if(ssh_bind_listen(b) < 0)
        return session_error(b, "listen");
    
    SSH_SESSION *s = ssh_bind_accept(b);
    if(!s)
        return session_error(b, "accept");
    if(ssh_accept(s) < 0)
        return session_error(s, "handshake");
    
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
            return session_error(s, "session");
        }
    }
}

void server_handle_message(SSH_MESSAGE *m, int type, int subtype, int *state)
{
    int handled = 0;
    if((*state == SERVER_CONNECTED) && (type == SSH_REQUEST_AUTH) && (subtype == SSH_AUTH_METHOD_PUBLICKEY))
    {
        ssh_public_key key = ssh_message_auth_publickey(m);
        ssh_string keystr = publickey_to_string(key);
        char *keyhash = pubkey_hash(keystr);
        int has_sig = ssh_message_auth_sig_state(m);
        if(has_sig == 0)
        {
            if(authenticate(keyhash, 1))
            {
                //FIXME: type detection
                ssh_string algostr = string_from_char("ssh-rsa");
                ssh_message_auth_reply_pk_ok(m, algostr, keystr);
                string_free(algostr);
                handled = 1;
            }
        }
        else if(has_sig == 1)
        {
            if(authenticate(keyhash, 0))
            {
                fprintf(stderr, "! authenticated %s\n", keyhash);
                ssh_message_auth_reply_success(m, 0);
                *state = SERVER_AUTHENTICATED;
            }
            else
            {
                ssh_message_reply_default(m);
                *state = SERVER_CLOSED;
            }
            handled = 1;
        }
        string_free(keystr);
        free(keyhash);
    }
    else if((*state == SERVER_AUTHENTICATED) && (type == SSH_REQUEST_CHANNEL_OPEN) && (subtype == SSH_CHANNEL_SESSION))
    {
        fprintf(stderr, "! channel-opened\n");
        ssh_channel chan = ssh_message_channel_request_open_reply_accept(m);
        if(chan)
        {
            ssh_buffer buf = buffer_new();
            int read;
            do
            {
                read = channel_read_buffer(chan, buf, 0, 0);
                if(read > 0)
                    write(1, buffer_get(buf), buffer_get_len(buf));
            } while (read > 0);
            buffer_free(buf);
        }
        channel_close(chan);
        *state = SERVER_CLOSED;
        handled = 1;
    }
    if(!handled)
        ssh_message_reply_default(m);
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