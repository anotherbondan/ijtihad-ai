from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "qa_pair" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "answer_id" INT NOT NULL REFERENCES "chatmessage" ("id") ON DELETE CASCADE,
    "question_id" INT NOT NULL REFERENCES "chatmessage" ("id") ON DELETE CASCADE
);
        ALTER TABLE "user" ADD "password" VARCHAR(128) NOT NULL;
        ALTER TABLE "user" ADD "email" VARCHAR(100) NOT NULL UNIQUE;
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_user_email_1b4f1c" ON "user" ("email");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "uid_user_email_1b4f1c";
        ALTER TABLE "user" DROP COLUMN "password";
        ALTER TABLE "user" DROP COLUMN "email";
        DROP TABLE IF EXISTS "qa_pair";"""
