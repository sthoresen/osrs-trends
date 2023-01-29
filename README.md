# osrs-trends
Finds good investments in the game OSRS

[Oldschool runescape](https://oldschool.runescape.com/) is game with a vibrant in-game economy featuring free trade and a clearing house called the Grand Exchange. Profits can be made through trading in a variety of ways, but this program focuses on medium term (weeks to months) range trading. It is not possible to enter trades automatically (expect if you are using bots, which is against Runescapes ToS), and thus the market is very inefficient. "Flipping" items is a popular activity amongst players, and some bots. It consists of buying and selling the same item rapidly, profiting a small margin. However, to my knowledge, there are no competing longer term trading programs and few players, meaning there is great opportunity to be found.

## Usage

> python run.py

*(Parameters and config are implemented as constants in run.py)*

## Details

The program finds the list of all tradeable items and their price and volume history using the [Weird Gloop API](https://api.weirdgloop.org/).

The program considers the price chart of each item as a sinusoid function, and identifies the items with
* The biggest amplitudes
* The fastest frequencies
* The most consistent shapes
* A current price below the mean

A number of features are used to estimate these properties.

Note that some fundamental knowledge is recommended in order to use the algorithm, as items have dropped in price due to a recent game update may not recover.

![](https://github.com/sthoresen/osrs-trends/blob/main/backtest_plot.png)


The relatioship between feature scoring and simulated backtested returns


<img src="https://github.com/sthoresen/osrs-trends/blob/main/coal.png" width="50%" alt="Identification of extremal and zero points" />
Identification of extremal and zero points

## In progress

* Use long term historic volume to get more realistic backtesting results by simulating slippage.
* Use higher frequency trading data, available for recent dates, to calculate intra-day volatility and get better entry/exit prices
* Calculate when to sell investments based on opportunity cost in relation to other items

