from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Lot(Base):
    __tablename__ = "lots"
    __table_args__ = (UniqueConstraint("lot_no", "stage", name="uq_lot_stage"),)

    id = Column(Integer, primary_key=True)
    lot_no = Column(String(64), nullable=False, index=True)
    stage = Column(String(32), nullable=False)
    bin = Column(Integer, default=1)
    traveler_qty = Column(Integer, default=0)
    lot_start_date = Column(String(32))
    temperature = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    sum_files = relationship("SumFile", back_populates="lot", cascade="all, delete-orphan")
    test_rounds = relationship("TestRound", back_populates="lot", cascade="all, delete-orphan")
    die_records = relationship("DieRecord", back_populates="lot", cascade="all, delete-orphan")
    chip_logs = relationship("ChipLog", back_populates="lot", cascade="all, delete-orphan")


class SumFile(Base):
    __tablename__ = "sum_files"
    __table_args__ = (UniqueConstraint("lot_id", "test_mode", name="uq_lot_test_mode"),)

    id = Column(Integer, primary_key=True)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    filename = Column(String(256), nullable=False)
    test_mode = Column(String(32), nullable=False)
    round_key = Column(String(32), nullable=False)
    sub_batch = Column(Integer, default=1)
    input_qty = Column(Integer, default=0)
    pass_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    yield_pct = Column(Float, default=0.0)
    start_time = Column(String(32))
    report_date = Column(String(32))
    file_path = Column(String(512))
    parsed_at = Column(DateTime, default=datetime.utcnow)

    lot = relationship("Lot", back_populates="sum_files")


class TestRound(Base):
    __tablename__ = "test_rounds"
    __table_args__ = (UniqueConstraint("lot_id", "round_key", name="uq_lot_round"),)

    id = Column(Integer, primary_key=True)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    round_key = Column(String(32), nullable=False)
    input_qty = Column(Integer, default=0)
    pass_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    yield_pct = Column(Float, default=0.0)
    start_time = Column(String(32))
    report_date = Column(String(32))
    sub_file_count = Column(Integer, default=1)
    is_merged = Column(Integer, default=1)

    lot = relationship("Lot", back_populates="test_rounds")
    bin_summaries = relationship("BinSummary", back_populates="round", cascade="all, delete-orphan")
    site_counters = relationship("SiteCounter", back_populates="round", cascade="all, delete-orphan")
    die_records = relationship("DieRecord", back_populates="round", cascade="all, delete-orphan")


class BinSummary(Base):
    __tablename__ = "bin_summaries"

    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey("test_rounds.id"), nullable=False)
    sw_category = Column(Integer)
    hw_bin = Column(Integer)
    code = Column(Integer)
    description = Column(String(64))
    count = Column(Integer, default=0)
    percent = Column(Float, default=0.0)

    round = relationship("TestRound", back_populates="bin_summaries")


class SiteCounter(Base):
    __tablename__ = "site_counters"

    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey("test_rounds.id"), nullable=False)
    site_no = Column(Integer)
    counter = Column(Integer, default=0)
    pass_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    yield_pct = Column(Float, default=0.0)

    round = relationship("TestRound", back_populates="site_counters")


class DieRecord(Base):
    __tablename__ = "die_records"

    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey("test_rounds.id"), nullable=False)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    die_id = Column(String(64), nullable=False, index=True)
    barcode = Column(String(64), index=True)
    site = Column(Integer)
    error_code = Column(Integer)
    software_bin = Column(Integer)
    boot_on = Column(String(16))
    booton = Column(String(32))
    tested = Column(String(32))
    tj = Column(String(64))
    bios_time = Column(String(32))
    test_time = Column(String(32))
    temperature = Column(Integer)
    round_key = Column(String(32))
    test_mode = Column(String(32))

    round = relationship("TestRound", back_populates="die_records")
    lot = relationship("Lot", back_populates="die_records")
    chip_logs = relationship("ChipLog", back_populates="die_record")


class ChipLog(Base):
    __tablename__ = "chip_logs"
    __table_args__ = (
        Index("ix_chip_log_match", "lot_id", "test_mode", "site", "primary_die_id", "barcode"),
    )

    id = Column(Integer, primary_key=True)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    test_mode = Column(String(32), nullable=False)
    round_key = Column(String(32), nullable=False)
    sub_batch = Column(Integer, default=1)
    site = Column(Integer)
    primary_die_id = Column(String(64), nullable=False, index=True)
    barcode = Column(String(64), index=True)
    pf = Column(String(8))
    soft_bin = Column(Integer)
    test_time = Column(String(32))
    test_start = Column(String(32))
    file_path = Column(String(512))
    die_record_id = Column(Integer, ForeignKey("die_records.id"), nullable=True)
    parsed_at = Column(DateTime, default=datetime.utcnow)

    lot = relationship("Lot", back_populates="chip_logs")
    die_record = relationship("DieRecord", back_populates="chip_logs")
    onetests = relationship("OneTest", back_populates="chip_log", cascade="all, delete-orphan")
    die_ids = relationship("ChipLogDieId", back_populates="chip_log", cascade="all, delete-orphan")


class OneTest(Base):
    __tablename__ = "onetests"

    id = Column(Integer, primary_key=True)
    chip_log_id = Column(Integer, ForeignKey("chip_logs.id"), nullable=False)
    test_txt = Column(String(128))
    pattern = Column(String(64))
    result = Column(String(64))
    pf = Column(String(8))
    test_time_ms = Column(Integer, default=0)

    chip_log = relationship("ChipLog", back_populates="onetests")


class ChipLogDieId(Base):
    __tablename__ = "chip_log_die_ids"

    id = Column(Integer, primary_key=True)
    chip_log_id = Column(Integer, ForeignKey("chip_logs.id"), nullable=False)
    die_id_str = Column(String(64))
    die_id_name = Column(String(64))
    lot = Column(String(32))
    wafer = Column(String(16))
    x = Column(String(16))
    y = Column(String(16))
    ordinal = Column(Integer, default=1)

    chip_log = relationship("ChipLog", back_populates="die_ids")


class ImportLog(Base):
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True)
    action = Column(String(32))
    filename = Column(String(256))
    status = Column(String(16))
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
