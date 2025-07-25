FROM jupyter/minimal-notebook:python-3.11

# Switch to root to install system dependencies including build tools, then switch back to the notebook user
USER root
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Syntactiq custom packages (as root to avoid permission issues)
COPY syntactiq_additions/ /tmp/syntactiq_additions/
RUN pip install --no-cache-dir /tmp/syntactiq_additions/syntactiq_utils-0.2.0-py3-none-any.whl && \
    pip install --no-cache-dir /tmp/syntactiq_additions/syntactiq_theme-0.1.0-py3-none-any.whl && \
    rm -rf /tmp/syntactiq_additions/

# Switch back to notebook user for Jupyter dependencies
USER ${NB_UID}

# Install Python dependencies according to the official jupyter-mcp-server documentation
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "jupyterlab==4.4.1" \
    "jupyter-collaboration==4.0.2" \
    "ipykernel" && \
    pip uninstall -y pycrdt datalayer_pycrdt && \
    pip install "datalayer_pycrdt==0.12.17"

# Install comprehensive data science and machine learning libraries
RUN pip install --no-cache-dir \
    # Core Data Science Stack
    "numpy>=1.24.0,<2.2.0" \
    "pandas>=2.1.0,<2.2.0" \
    "scipy>=1.10.0,<1.14.0" \
    "scikit-learn>=1.5.0,<1.8.0" \
    # Database & Analytics
    "duckdb>=0.9.0,<0.11.0" \
    "sqlalchemy>=2.0.0,<3.0.0" \
    "pyarrow>=12.0.0,<16.0.0" \
    # Visualization Libraries
    "matplotlib>=3.7.0,<3.10.0" \
    "seaborn>=0.12.0,<0.14.0" \
    "plotly>=5.15.0,<6.0.0" \
    "bokeh>=3.2.0,<3.6.0" \
    # Deep Learning Frameworks  
    "tensorflow>=2.16.0,<2.20.0" \
    "torch>=2.0.0,<2.6.0" \
    "torchvision>=0.15.0,<0.21.0" \
    # Traditional ML & Boosting
    "xgboost>=1.7.0,<2.2.0" \
    "lightgbm>=4.0.0,<4.6.0" \
    "catboost>=1.2.0,<1.3.0" \
    # Natural Language Processing
    "nltk>=3.8.0,<3.10.0" \
    "spacy>=3.6.0,<3.9.0" \
    "transformers>=4.30.0,<4.47.0" \
    # Image Processing
    "opencv-python>=4.8.0,<4.11.0" \
    "pillow>=10.0.0,<12.0.0" \
    "scikit-image>=0.21.0,<0.25.0" \
    # Statistics & Scientific Computing
    "statsmodels>=0.14.0,<0.16.0" \
    "sympy>=1.12.0,<1.14.0" \
    # Interactive Widgets & Progress
    "ipywidgets>=8.0.0,<8.2.0" \
    "tqdm>=4.65.0,<4.67.0" \
    # Data Manipulation & I/O
    "openpyxl>=3.1.0,<3.3.0" \
    "xlrd>=2.0.0,<2.1.0" \
    "h5py>=3.9.0,<3.13.0" \
    # Web & APIs
    "requests>=2.31.0,<2.34.0" \
    "beautifulsoup4>=4.12.0,<4.14.0" \
    "fastapi>=0.100.0,<0.118.0" \
    # Feature Engineering & Preprocessing
    "feature-engine>=1.6.0,<1.9.0" \
    "imbalanced-learn>=0.11.0,<0.13.0" \
    # Time Series Analysis
    "prophet>=1.1.4,<1.2.0"