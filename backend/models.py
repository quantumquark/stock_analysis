from sqlalchemy import Column, String, Float, Date, Integer, BigInteger, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "stock_data.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

Base = declarative_base()


class Stock(Base):
    __tablename__ = "stocks"

    ticker = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    sector = Column(String)
    industry = Column(String)

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "name": self.name,
            "sector": self.sector,
            "industry": self.industry,
        }


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)

    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_ticker_date"),)

    def to_dict(self):
        return {
            "date": self.date.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


def get_engine():
    return create_engine(DATABASE_URL, echo=False)


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    print(f"Database initialized at: {DB_PATH}")
