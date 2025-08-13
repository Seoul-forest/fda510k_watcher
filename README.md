# FDA 510(k) HTML Watcher

A Python application that automatically monitors the FDA 510(k) medical device approval database and sends email notifications when new approval information is detected.

## 🎯 Key Features

- **Automatic Monitoring**: Automatically detects new 510(k) approval information from FDA website
- **Multi-Condition Search**: Search based on Product Code and Applicant Name
- **Email Notifications**: Sends HTML table format emails when new information is detected
- **Duplicate Prevention**: Stores seen K-numbers to prevent duplicate notifications
- **Web Scraping**: Reliable web data collection using Playwright

## 🚀 Installation & Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd fda510k_watcher
```

### 2. Python Environment Setup
```bash
# Using conda environment (recommended)
conda create -n py311 python=3.11
conda activate py311

# Or using venv
python -m venv venv
source venv/bin/activate  # macOS/Linux
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Environment Variables Configuration
Create a `.env` file and add the following content:

```env
# SMTP Email Settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
MAIL_TO=recipient@example.com

# Product Codes to Monitor (comma-separated)
WATCH_PRODUCT_CODES=JAK,IZI,LLZ

# Applicants to Monitor (comma-separated)
WATCH_APPLICANTS=Medtronic,Johnson & Johnson,Stryker
```

**Important Notes for Gmail Users:**
- You must enable 2-factor authentication
- Generate an app password and use it for `SMTP_PASS`

## 📊 Usage

### Basic Execution
```bash
python fda_510k_html_watch.py
```

### Monitoring Conditions Setup
- **Product Code**: Search by specific medical device classification codes
- **Applicant**: Search by company names (partial match)

### Results
- Email notifications are sent when new 510(k) approvals are detected
- Processed K-numbers are stored in `fda_510k_html_state.json`

## 🔧 Main Components

- **`fda_510k_html_watch.py`**: Main program
- **`.env`**: Environment variables configuration (not included in Git)
- **`requirements.txt`**: Required Python packages
- **`.gitignore`**: Files to exclude from Git

## 📁 File Structure
```
fda510k_watcher/
├── fda_510k_html_watch.py    # Main program
├── .env                      # Environment variables (local only)
├── .gitignore               # Git exclusion files
├── requirements.txt          # Python package list
└── README.md                # Project documentation
```

## 🛠️ Technical Details

### Web Scraping
- Uses Playwright for reliable browser automation
- Handles pagination to collect all search results
- Robust error handling for website structure changes

### Data Parsing
- BeautifulSoup for HTML parsing
- Extracts K-number, device name, applicant, product code, decision date, and detail URL
- Handles various table layouts and formats

### Email System
- SMTP-based email delivery
- HTML formatted tables for easy reading
- Configurable email templates

## ⚠️ Important Notes

- **Never commit the `.env` file** as it contains sensitive information
- FDA website structure may change, requiring regular verification
- Use appropriate intervals when running web scraping to be respectful
- This tool is for educational and research purposes

## 🔒 Security

- Environment variables are loaded from `.env` file (not committed to Git)
- SMTP credentials are stored securely
- No sensitive data is logged or exposed

## 📝 License

This project is created for educational and research purposes.

## 🤝 Contributing

- Report bugs by creating issues
- Suggest new features through issue discussions
- Follow standard Git workflow for contributions

## 📞 Support

For questions or issues:
1. Check existing issues in the repository
2. Create a new issue with detailed description
3. Include error messages and system information

## 🔄 Future Enhancements

- [ ] Add web interface for configuration
- [ ] Implement scheduled monitoring
- [ ] Add more search criteria
- [ ] Create dashboard for monitoring results
- [ ] Add export functionality for data analysis
