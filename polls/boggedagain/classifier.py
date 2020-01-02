import os, pickle, random, nltk, math, sqlite3, time

def news_features(newstext):
    newstext = newstext.lower()
    news_list = set(newstext.split())
    features = {}
    # analyst downgrade (AD)
    features['AD'] = (('analyst' in news_list or 'analysts' in news_list)
                     and ('downgrade' in news_list or 'rating' in news_list or 'estimate' in news_list)) \
                     or newstext.find('sell rating')
    # bankruptcy (B)
    features['B'] = 'bankruptcy' in news_list
    # competitor product(CP) -WIP
    # features['CP'] = '' in news_list
    # company scandal (CS)
    features['CS'] = 'investigation' in newstext or 'federal probe' in newstext or 'accounting practice' in newstext
    # leadership change(LC)
    features['LC'] = 'step down' in newstext or 'leaving the company' in newstext or 'take over' in newstext \
                     or 'now-former' in newstext or 'leadership transition' in newstext
    # lowered guidance(LG)
    features['LG'] = 'forecast downward' in newstext or 'adjustment in forward earnings' in newstext or \
                     ('guidance' in newstext and ('softer' in newstext or 'reduce' in newstext))
    # lost lawsuit(LL)
    features['LL'] = 'appeal' in news_list or 'lawsuit' in news_list
    # leadership scandal(LS)
    features['LS'] = 'scandal' in news_list or ('violate' in newstext and 'company policy' in newstext)
    # merger(M)
    features['M'] = 'merger' in newstext or 'acquisition' in newstext or 'buy startup' in newstext \
                    or 'takeover' in newstext
    # new options(NO)
    features['NO'] = 'new options' in newstext
    # public offering(PO)
    features['PO'] = 'public offering' in newstext
    # regulation(R)
    features['R'] = 'regulation' in news_list or 'federal communications commission' in newstext \
                    or 'justice department' in newstext or 'antitrust' in newstext or 'anti-trust' in newstext
    # restructuring/layoff(RL)
    features['RL'] = 'layoff' in news_list or 'restructuring' in news_list \
                     or ('lay' in news_list and 'off' in news_list) or 'refinance' in news_list
    # revenuve miss(RM)
    features['RM'] = 'revenue' in news_list and 'missed' in news_list or ('missed' in newstext and 'earnings estimates' in newstext) \
                     or (('weaker-than-expected' in newstext or 'wider-than-expected' in newstext) and 'earnings' in newstext)
    # sector dump(SD)
    features['SD'] = 'sector' in news_list or 'selloff' in news_list
    # stock split(SS)
    features['SS'] = 'split' in news_list
    # trump(T)
    features['T'] = 'trump' in news_list
    # trade war(TW)
    features['TW'] = 'tariffs' in news_list or 'trade' in news_list
    return features

def generate_classifier():
    category_list = ['AD','B','CS','LC','LG','LL','LS','M','R','RL','RM','SD','SS','T','TW']
    feature_set = []
    news_text = []
    for category in category_list:
        for entry in os.scandir(f'../../trainer/{category}/'):
            if not entry.name.startswith('.') and entry.is_file() and entry.name.find('labeled') != -1:
                with open(f'../../trainer/{category}/{entry.name}') as f:
                    data = f.read()
                    news_text.append([data, category, entry.name])
                    feature_set.append([news_features(data), category])
                print(entry.name)
    random.shuffle(feature_set)
    train_index = math.ceil(len(feature_set)/2)
    train_set = feature_set[::train_index]
    test_set = feature_set[train_index::]
    print(train_index)
    classifier = nltk.NaiveBayesClassifier.train(train_set)
    accuracy = math.ceil(nltk.classify.accuracy(classifier, test_set)*10000)/100
    classifier.show_most_informative_features(5)
    errors = []
    for (text, tag, name) in news_text:
        guess = classifier.classify(news_features(text))
        if guess != tag:
            errors.append((tag, guess, name))

    for (tag, guess, name) in sorted(errors):
        print('correct={:<8} guess={:<8s} name={:<30}'.format(tag, guess, name))
    f = open('../../my_classifier.pickle', 'wb')
    pickle.dump(classifier, f)
    f.close()

    # SQLite shenanigans
    connection = sqlite3.connect("classifier.db")
    cursor = connection.cursor()
    sql_command = """
    CREATE TABLE versions ( 
    time text, 
    'training set size' real, 
    accuracy real);"""
    # cursor.execute(sql_command) # this step was the original setup for the table in that database- no longer needed

    sql_command = f"""INSERT INTO versions(time, 'training set size', accuracy) 
    VALUES ({time.strftime("%Y%m%d",time.gmtime())}, {train_index}, {accuracy});"""
    cursor.execute(sql_command)

    cursor.execute("SELECT * FROM versions")
    print("fetchall:")
    result = cursor.fetchall()
    for r in result:
        print(r)
    connection.commit()
    connection.close()

#generate_classifier()
