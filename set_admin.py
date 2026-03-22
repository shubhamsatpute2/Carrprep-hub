#!/usr/bin/env python
"""
Script to set a user as admin in the CareerPrep Hub database.

Usage: python set_admin.py <username>
Example: python set_admin.py john_doe
"""

import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models import User as UserModel

DATABASE_URL = "sqlite+aiosqlite:///./careerprep.db"


async def set_admin_user(username: str):
    """Set a user as admin."""
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.username == username)
            )
            user = result.scalar_one_or_none()

            if user:
                user.is_admin = True
                await session.commit()
                print(f"✓ User '{username}' is now an admin!")
            else:
                print(f"✗ User '{username}' not found")
                sys.exit(1)

        await engine.dispose()
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        sys.exit(1)


async def revoke_admin_user(username: str):
    """Revoke admin privileges from a user."""
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.username == username)
            )
            user = result.scalar_one_or_none()

            if user:
                if user.is_admin:
                    user.is_admin = False
                    await session.commit()
                    print(f"✓ Admin privileges revoked for '{username}'!")
                else:
                    print(f"✗ User '{username}' is not an admin")
            else:
                print(f"✗ User '{username}' not found")
                sys.exit(1)

        await engine.dispose()
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        sys.exit(1)


async def list_admins():
    """List all admin users."""
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.is_admin == True)
            )
            admins = result.scalars().all()

            if admins:
                print("Admin Users:")
                print("-" * 50)
                for admin in admins:
                    print(f"  • {admin.username} ({admin.email})")
                print("-" * 50)
                print(f"Total admins: {len(admins)}")
            else:
                print("No admin users found")

        await engine.dispose()
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Admin User Management Script")
        print("=" * 50)
        print("\nUsage:")
        print("  Make user admin:     python set_admin.py <username>")
        print("  Revoke admin:        python set_admin.py --revoke <username>")
        print("  List all admins:     python set_admin.py --list")
        print("\nExample:")
        print("  python set_admin.py john_doe")
        sys.exit(1)

    if sys.argv[1] == "--list":
        asyncio.run(list_admins())
    elif sys.argv[1] == "--revoke":
        if len(sys.argv) < 3:
            print("Error: Please specify username")
            print("Usage: python set_admin.py --revoke <username>")
            sys.exit(1)
        asyncio.run(revoke_admin_user(sys.argv[2]))
    else:
        asyncio.run(set_admin_user(sys.argv[1]))


if __name__ == "__main__":
    main()
