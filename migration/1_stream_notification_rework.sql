ALTER TABLE "admin_roles"
    DROP COLUMN "name",
    DROP COLUMN "guild_name"
;

ALTER TABLE "channel_streams"
    RENAME TO "user_channels";

ALTER TABLE "user_channels"
    RENAME COLUMN "stream_id" TO "user_id";
ALTER TABLE "user_channels"
    RENAME CONSTRAINT "channel_streams_channel_id_fkey" TO "user_channels_channel_id_fkey";
ALTER TABLE "user_channels"
    RENAME CONSTRAINT "channel_streams_stream_id_fkey" TO "user_channels_user_id_fkey";
ALTER TABLE "user_channels"
    RENAME CONSTRAINT "channel_streams_stream_id_channel_id" TO "user_channels_user_id_channel_id";


ALTER TABLE "extensions"
    DROP COLUMN "guild_name"
;

ALTER TABLE "prefixes"
    DROP COLUMN "guild_name"
;

ALTER TABLE "streams" RENAME TO "users";
ALTER TABLE "users" RENAME COLUMN "name" TO "login";
ALTER TABLE "users" RENAME CONSTRAINT "streams_pkey" TO "users_pkey";
