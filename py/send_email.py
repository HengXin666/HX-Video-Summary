"""
QQ邮箱发送工具
通过 QQ SMTP 发送带附件的邮件，用于 GitHub Actions 工作流。
"""

import argparse
import smtplib
import sys
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path

QQ_SMTP_HOST = "smtp.qq.com"
QQ_SMTP_PORT = 465


def send_email(
    sender: str,
    password: str,
    to: str,
    subject: str,
    body: str,
    attachment: str | None = None,
    cc: str | None = None,
) -> bool:
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment:
        path = Path(attachment)
        if not path.exists():
            print(f"错误: 附件不存在: {attachment}")
            return False
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{path.name}"',
            )
            msg.attach(part)

    recipients = [to]
    if cc:
        recipients.append(cc)

    try:
        with smtplib.SMTP_SSL(QQ_SMTP_HOST, QQ_SMTP_PORT) as server:
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        print(f"邮件发送成功: {to}" + (f" (抄送: {cc})" if cc else ""))
        return True
    except smtplib.SMTPAuthenticationError:
        print("错误: QQ邮箱SMTP认证失败，请检查邮箱地址和授权码")
        return False
    except Exception as e:
        print(f"错误: 邮件发送失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="QQ邮箱发送工具")
    parser.add_argument("--sender", required=True, help="发件人QQ邮箱")
    parser.add_argument("--password", required=True, help="QQ邮箱SMTP授权码")
    parser.add_argument("--to", required=True, help="收件人邮箱")
    parser.add_argument("--cc", help="抄送邮箱")
    parser.add_argument("--subject", required=True, help="邮件主题")
    parser.add_argument("--body", required=True, help="邮件正文")
    parser.add_argument("--attachment", help="附件路径")
    args = parser.parse_args()

    if not send_email(
        sender=args.sender,
        password=args.password,
        to=args.to,
        subject=args.subject,
        body=args.body,
        attachment=args.attachment,
        cc=args.cc,
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
